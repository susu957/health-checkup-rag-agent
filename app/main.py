import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel   # ← 确保这行在最上面

from app.agent_graph import agent_executor
from app.rag_service import ask_question

# 禁用默认 /docs，手动接管
app = FastAPI(
    title="养老院体检预约与RAG问答",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
    )



# ==================== 请求模型 ====================

class ChatRequest(BaseModel):
    message: str
    user_id: int | None = None
    session_id: str | None = None

class AskRequest(BaseModel):
    question: str | None = None
    questions: list[str] | None = None


# ==================== 路由 ====================

@app.post("/api/v1/chat")
def chat(req: ChatRequest):
    """统一 Agent 入口：预约 / 查报告 / 问答全部走 langgraph"""
    try:
        from langchain_core.messages import HumanMessage
        result = agent_executor.invoke(
            {"messages": [HumanMessage(content=req.message)]}
        )

        # ===== 调试打印：查看 agent 内部消息流 =====
        messages = result.get("messages", [])
        print(f"\n[DEBUG_API] 共 {len(messages)} 条消息")
        for i, msg in enumerate(messages):
            tc = getattr(msg, "tool_calls", None)
            print(f"[DEBUG_API] msg[{i}] type={msg.type} tool_calls={tc}")
            if tc:
                for t in tc:
                    print(f"[DEBUG_API]   -> tool={t.get('name')} args={t.get('args')}")
        # ==========================================

        reply = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content:
                reply = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        if not reply and "answer" in result:
            reply = str(result["answer"])
        if not reply and isinstance(result, dict) and "messages" in result:
            for msg in result["messages"]:
                if hasattr(msg, "content") and msg.content:
                    reply = str(msg.content)
                    break

        print(f"[DEBUG] final reply: {reply[:200]}")

        # 提取本次请求中所有被调用的工具名称
        # 在 return JSONResponse 之前
        called_tools = []
        for msg in messages:  # messages 是 graph 执行结果中的消息列表
            tc = getattr(msg, "tool_calls", None)
            if tc and isinstance(tc, list):
                for t in tc:
                    if isinstance(t, dict) and t.get("name"):
                        called_tools.append(t["name"])
                    elif hasattr(t, "name"):
                        called_tools.append(t.name)

        return JSONResponse(
            content={
                "reply": reply,
                "tool_calls": called_tools,  # 这里应该包含所有被调用的工具
            },
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/ask")
def rag_ask(req: AskRequest):
    """纯 RAG 问答入口（不调用业务工具）"""
    if req.questions:
        results = [ask_question(q) for q in req.questions]
        return JSONResponse(
            content={"results": results},
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    if req.question:
        answer = ask_question(req.question)
        return JSONResponse(
            content={"answer": answer},
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
    return JSONResponse(
        content={"error": "缺少 question 或 questions"},
        status_code=400,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)