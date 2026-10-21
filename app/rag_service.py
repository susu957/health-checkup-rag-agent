import os
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS

EMBED_MODEL = "BAAI/bge-small-zh-v1.5"          # 已确认与 ingest.py 一致，不要动
FAISS_DIR = str(Path(__file__).parent / "faiss_index")  # ← 锚定到 app\faiss_index
MIN_DISTANCE = 1.5      # ← 放宽，原来 1.2 太严
TOP_K = 4               # ← 多召回一条

emb = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

llm = ChatDeepSeek(
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    model="deepseek-chat",          # ← 官方可用模型名
    temperature=0,
)

def load_faiss():
    return FAISS.load_local(FAISS_DIR, emb, allow_dangerous_deserialization=True)

def ask_question(question: str):
    vectorstore = load_faiss()
    docs_with_score = vectorstore.similarity_search_with_score(question, k=TOP_K)

    ok = [(d, s) for d, s in docs_with_score if s <= MIN_DISTANCE]
    if not ok:
        # 调试用：把实际召回的距离打出来，方便判断阈值卡在哪
        print("[debug] top scores:", [round(float(s), 3) for _, s in docs_with_score])
        return {"answer": "知识库中暂无相关信息，请补充资料后再试。", "sources": []}

    ctx, srcs = [], []
    for i, (d, score) in enumerate(ok, 1):
        ctx.append(f"[S{i}] {d.page_content}")
        srcs.append({
            "id": f"S{i}",
            "source": d.metadata.get("source", "未知"),
            "snippet": d.page_content[:200],
            "score": float(score),
        })

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "你是养老院体检知识库助手，严格依据【参考资料】作答。"
         "资料不足时回答“知识库中暂无相关信息”，并在答案末尾标注来源编号。"),
        ("human", "参考资料：\n{context}\n\n问题：{question}"),
    ])
    chain = prompt | llm | StrOutputParser()
    ans = chain.invoke({"context": "\n".join(ctx), "question": question})
    return {"answer": ans, "sources": srcs}