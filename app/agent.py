import os
from dotenv import load_dotenv

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from app.tools import TOOLS, execute_tool

load_dotenv()

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-flash"),
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    openai_api_base=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
)
SYSTEM_PROMPT = """你是养老院体检预约与报告管理助手。
你可以帮老人查询档案、预约体检、查看报告。
调用工具前要先确认老人ID、日期、时间段等关键信息是否齐全；
信息不足时先追问用户，不要编造参数。"""

agent = create_react_agent(
    llm,
    tools=TOOLS,
    prompt=SYSTEM_PROMPT,   # 这里改成 prompt
)