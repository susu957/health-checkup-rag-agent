import os
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

# 兼容不同 langgraph 版本的导入路径
try:
    from langgraph.graph import MessagesState
except ImportError:
    from langgraph.graph.state import MessagesState

# 尝试导入 OpenAI 客户端（直接调用 API，不经过 LangChain 的 bind_tools）
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from app.tools import TOOLS
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

# ==================== 环境变量加载 ====================
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=dotenv_path, verbose=True)

LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-flash")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    raise RuntimeError(f"未设置 DEEPSEEK_API_KEY，请检查 {dotenv_path} 文件")

# ==================== 创建 OpenAI 客户端（直接调用 API） ====================
if OPENAI_AVAILABLE:
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
else:
    raise RuntimeError("需要安装 openai 包，请运行: pip install openai")

# ==================== System Prompt ====================
SYSTEM_PROMPT = """你必须严格遵守以下规则：

1. 【强制工具调用】当用户请求涉及预约、查档案、查报告、查排期、健康知识等问题时，
   你必须立即调用对应工具，严禁自己编造答案或问用户"请告诉我XX"

2. 【参数抽取优先】从用户输入中抽取可用参数，即使信息不完整也要先调用工具。
   工具会返回参数缺失的错误提示，由你来根据错误提示决定下一步，
   而不是由你直接问用户。

3. 【禁止自我推脱】不要说"我需要更多信息"、"请告诉我"、"我无法确认"等推脱话术。
   你的职责是调用工具获取数据，然后根据数据回复用户。

4. 【工具清单】你必须使用以下工具：
   - get_elderly_profile: 查老人档案（需要elderly_id）
   - get_appointments_by_date: 查某天预约排期（需要appointment_date）
   - book_appointment: 创建预约（需要elderly_id, package_id, appointment_date, time_slot）
   - query_report: 查体检报告（需要elderly_id）
   - create_report: 创建体检报告（需要appointment_id, summary）
   - check_availability: 查套餐号源余量（需要package_id, start_date）
   - answer_knowledge: 回答体检/健康知识问题（需要question）
   - rag_knowledge_search: 基于知识库文档回答体检、养老等相关知识问题（需要question）
     当用户询问体检流程、报告解读、慢病管理、健康知识等需要查阅文档的问题时调用此工具，
     它会从知识库文档中检索相关信息并生成回答。优先于 answer_knowledge 使用。

5. 工具返回结果后，用自然语言回复用户。

6. 如果工具返回错误（如参数缺失），根据错误信息决定是补充调用其他工具还是回复用户，
   但不要一开始就问用户要信息。

7. 【套餐名称映射规则】当用户预约体检套餐时，必须把套餐名称转换为 package_id：
   - "基础健康套餐" -> package_id = 1
   - "慢病管理套餐" -> package_id = 2
   - "康复护理套餐" -> package_id = 3
   如果用户未明确套餐名称，不得猜测 package_id，应追问确认。

8. 【预约工具调用规则】当用户请求预约体检时，必须调用 book_appointment 工具，
   并传入 elderly_id、appointment_date（YYYY-MM-DD格式）、time_slot、package_id 四个参数。
   严禁使用 get_elderly_profile 替代预约工具。
   预约的核心动作是"创建预约"，对应工具是 book_appointment，不是查档案。"""

# ==================== 工具注册调试 ====================
print(f"[DEBUG] TOOLS count: {len(TOOLS)}")
for i, tool in enumerate(TOOLS):
    print(f"[DEBUG] Tool[{i}]: name={tool.name}, type={type(tool)}")


# ==================== 将 LangChain 工具转为 OpenAI API 格式 ====================
def convert_tools(tools):
    """将 LangChain StructuredTool 列表转为 OpenAI tools 格式"""
    openai_tools = []
    for tool in tools:
        # 获取参数 schema
        if hasattr(tool, 'args_schema') and tool.args_schema is not None:
            try:
                parameters = tool.args_schema.schema()
            except Exception:
                parameters = {"type": "object", "properties": {}}
        else:
            parameters = {"type": "object", "properties": {}}

        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": getattr(tool, 'description', '') or '',
                "parameters": parameters,
            }
        })
    return openai_tools


# 转换工具定义
openai_tools = convert_tools(TOOLS)
print(f"\n[DEBUG] OpenAI tools 定义数量: {len(openai_tools)}")
for t in openai_tools:
    print(f"[DEBUG]   - {t['function']['name']}: {t['function']['description'][:60]}...")


# ==================== 消息格式转换 ====================
def messages_to_api(messages):
    """将 LangChain 消息列表转为 OpenAI API 格式"""
    api_messages = []
    for msg in messages:
        if msg.type == "system":
            api_messages.append({"role": "system", "content": msg.content})
        elif msg.type == "human":
            api_messages.append({"role": "user", "content": msg.content})
        elif msg.type == "ai":
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                # AI 消息包含工具调用
                tool_calls = []
                for tc in msg.tool_calls:
                    tool_calls.append({
                        "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"], ensure_ascii=False) if isinstance(tc["args"],
                                                                                                  dict) else str(
                                tc["args"]),
                        }
                    })
                api_messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                })
            else:
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                api_messages.append({"role": "assistant", "content": content})
        elif msg.type == "tool":
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            tool_call_id = getattr(msg, 'tool_call_id', None)
            if not tool_call_id:
                tool_call_id = f"call_{uuid.uuid4().hex[:8]}"
            api_messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
            })
    return api_messages


def api_response_to_ai_message(response):
    """将 OpenAI API 响应转为 LangChain AIMessage"""
    choice = response.choices[0]
    message = choice.message

    # 检查是否有工具调用
    tool_calls = []
    if hasattr(message, 'tool_calls') and message.tool_calls:
        for tc in message.tool_calls:
            # 解析参数
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except (json.JSONDecodeError, AttributeError):
                args = {}

            tool_calls.append({
                "id": tc.id if hasattr(tc, 'id') and tc.id else f"call_{uuid.uuid4().hex[:8]}",
                "name": tc.function.name,
                "args": args,
            })

    content = message.content if hasattr(message, 'content') and message.content else ""
    # FIX: 始终传列表（空列表也是合法的），不要传 None
    return AIMessage(content=content, tool_calls=tool_calls)


# ==================== 工具执行 ====================
def execute_tool_calls(tool_calls):
    """执行工具调用并返回 ToolMessage 列表"""
    tool_messages = []
    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        tool_id = tc.get("id", f"call_{uuid.uuid4().hex[:8]}")

        # 查找工具
        tool = None
        for t in TOOLS:
            if t.name == tool_name:
                tool = t
                break

        if tool is None:
            result = f"错误：未找到工具 '{tool_name}'"
            print(f"[DEBUG_TOOL] 未找到工具: {tool_name}")
        else:
            try:
                result = tool.invoke(tool_args)
                print(f"[DEBUG_TOOL] 工具 {tool_name} 执行成功")
            except Exception as e:
                result = f"工具执行失败 ({tool_name}): {str(e)}"
                print(f"[DEBUG_TOOL] 工具 {tool_name} 执行失败: {e}")

        # 创建 ToolMessage
        tool_messages.append(ToolMessage(
            content=str(result) if not isinstance(result, str) else result,
            tool_call_id=tool_id,
        ))
    return tool_messages


# ==================== 测试 API 工具调用能力 ====================
print("\n[DEBUG] === 测试 DeepSeek API 工具调用能力 ===")
test_messages = [
    {"role": "system", "content": "你是一个测试助手。"},
    {"role": "user", "content": "请调用 get_elderly_profile 工具查询编号为1的老人"},
]
try:
    test_response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=test_messages,
        tools=openai_tools,
        temperature=0.1,
    )
    test_msg = test_response.choices[0].message
    test_tc = getattr(test_msg, 'tool_calls', None)
    print(f"[DEBUG] API 测试响应 type: {type(test_msg).__name__}")
    print(f"[DEBUG] API 测试 tool_calls: {test_tc}")
    if test_tc:
        for tc in test_tc:
            print(f"[DEBUG]   -> function: {tc.function.name}, args: {tc.function.arguments}")
        print("[DEBUG] API 工具调用测试通过！")
    else:
        print("[DEBUG] WARNING: API 未返回工具调用，模型可能不支持 function calling")
        print(f"[DEBUG] API 响应内容: {str(test_msg.content)[:200]}")
except Exception as e:
    print(f"[DEBUG] API 测试失败: {e}")
    import traceback

    traceback.print_exc()
print("[DEBUG] === 测试结束 ===\n")


# ==================== 构建 StateGraph ====================
def chatbot(state):
    """调用 LLM（直接 API 调用 + 工具）并返回响应"""
    messages = list(state["messages"])

    # 检查是否已有 system 消息，没有就 prepend
    has_system = any(m.type == "system" for m in messages)
    if not has_system:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    # 转换为 API 格式
    api_messages = messages_to_api(messages)

    print(f"\n[DEBUG_CHATBOT] 准备发送 {len(api_messages)} 条消息给 LLM API")
    for i, m in enumerate(api_messages):
        role = m.get('role', '?')
        content = str(m.get('content', ''))[:100] if m.get('content') else '(null)'
        print(f"[DEBUG_CHATBOT]   [{i}] {role} | {content}")

    # 直接调用 OpenAI 兼容 API（带 tools 参数）
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=api_messages,
        tools=openai_tools,
        temperature=0.1,
    )

    # 转为 LangChain 消息
    ai_message = api_response_to_ai_message(response)

    print(f"\n[DEBUG_CHATBOT] LLM 响应:")
    print(f"[DEBUG_CHATBOT]   type={type(ai_message).__name__}")
    print(f"[DEBUG_CHATBOT]   tool_calls={getattr(ai_message, 'tool_calls', 'N/A')}")
    print(f"[DEBUG_CHATBOT]   content={str(ai_message.content)[:200]}")

    return {"messages": [ai_message]}


def should_continue(state):
    """判断是否需要继续调用工具"""
    messages = state["messages"]
    last = messages[-1]
    tc = getattr(last, "tool_calls", None)

    print(f"\n[DEBUG_ROUTER] 路由判断: last.type={type(last).__name__}, tool_calls={tc}")

    if tc:
        print("[DEBUG_ROUTER]   -> 有工具调用，路由到 tools 节点")
        return "tools"
    else:
        print("[DEBUG_ROUTER]   -> 无工具调用，结束图执行")
        return END


def tool_executor(state):
    """执行工具调用（替代 ToolNode，手动执行）"""
    messages = state["messages"]
    last = messages[-1]

    if hasattr(last, 'tool_calls') and last.tool_calls:
        tool_messages = execute_tool_calls(last.tool_calls)
        print(f"\n[DEBUG_TOOL_EXEC] 执行了 {len(tool_messages)} 个工具调用")
        for tm in tool_messages:
            print(f"[DEBUG_TOOL_EXEC]   {tm.tool_call_id}: {str(tm.content)[:150]}")
        return {"messages": tool_messages}

    print("[DEBUG_TOOL_EXEC] 无工具调用需要执行")
    return {"messages": []}


# 构建图
print("[DEBUG] 正在构建 StateGraph...")
graph = StateGraph(MessagesState)
graph.add_node("chatbot", chatbot)
graph.add_node("tools", tool_executor)

graph.add_edge(START, "chatbot")

# 兼容不同 langgraph 版本的 add_conditional_edges 签名
try:
    graph.add_conditional_edges("chatbot", should_continue)
except TypeError:
    graph.add_conditional_edges("chatbot", should_continue, {"tools": "tools", "end": END})

graph.add_edge("tools", "chatbot")

# 编译
agent_executor = graph.compile()

print("\n[DEBUG] Agent graph compiled successfully")
print(f"[DEBUG] Graph nodes: {list(graph.nodes.keys())}")