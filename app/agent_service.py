import json
import requests
from openai import OpenAI

from app.config import (
    DEEPSEEK_API_KEY,
    LLM_MODEL,
    DEEPSEEK_BASE_URL,
    JAVA_BASE_URL,
)
from app.tools import TOOLS
from app.rag_service import ask_question
from app.agent_graph import agent_executor

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

# 【修复2】注入强约束的 System Prompt
SYSTEM_PROMPT = """你是养老院体检预约系统的智能调度 Agent。

【决策铁律】
1. 用户要求【为某个老人预约体检】 -> 如果已知老人ID，直接调用 book_appointment；如果只知道姓名不知道ID，先调用 get_elderly_profile 查询ID。
2. 用户要求【查询某个老人的体检报告】 -> 调用 query_report（需要 elder_user_id）。
3. 用户要求【查询某个老人的档案信息】 -> 调用 get_elderly_profile。
4. 用户要求【查询某日期的预约情况】 -> 调用 get_appointments_by_date。
5. 用户要求【查询排期/剩余号源】 -> 调用 check_availability。
6. 用户问【通用知识】（体检流程、注意事项、报告解读方法、慢病管理） -> 必须调用 answer_knowledge。
7. 如果用户问题同时涉及操作和知识，优先执行操作步骤。
8. 如果参数不全（如缺少老人ID、日期、套餐ID），不要瞎猜，可以先追问用户补全，或者尝试调用工具让后端处理。

【可用工具】
"""


def _java_get(path: str, params: dict | None = None, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.get(f"{JAVA_BASE_URL}{path}", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


# 【修复3】补全所有工具的分发逻辑
def dispatch_tool(name: str, args: dict, token: str | None = None):
    try:
        if name == "check_availability":
            return _java_get(
                "/api/appointment/availability",
                {"packageId": args["package_id"], "days": args.get("days", 7)},
                token,
            )

        if name == "query_report":
            return _java_get(
                "/api/report/latest",
                {"elderUserId": args["elder_user_id"]},
                token,
            )

        if name == "get_elderly_profile":
            return _java_get(
                "/api/elderly/profile",
                {"elderlyId": args["elderly_id"]},
                token,
            )

        if name == "get_appointments_by_date":
            return _java_get(
                "/api/appointment/list",
                {"date": args["appointment_date"]},
                token,
            )

        if name == "book_appointment":
            return {
                "status": "pending_confirm",
                "data": args,
                "tip": "请用户确认后再提交预约",
            }

        if name == "answer_knowledge":
            return ask_question(args["question"])

        if name == "create_report":
            return {"status": "success", "message": "报告创建逻辑待接入 Java 端"}

        raise ValueError(f"未知工具: {name}")
    except Exception as e:
        return {"error": f"工具执行失败: {str(e)}"}


def chat(user_msg: str, history: list | None = None, token: str | None = None):
    messages = history or []
    messages.append({"role": "user", "content": user_msg})

    result = agent_executor.invoke({"messages": messages})

    final_answer = result["messages"][-1].content
    return final_answer, result["messages"]