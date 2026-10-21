import os
from pathlib import Path

# 国内下载 HuggingFace 模型超时，先设镜像（必须在 import embeddings 之前）
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 路径锚定：不管你从哪个目录启动，永远指向 app\data 和 app\faiss_index
DEFAULT_DATA_DIR = Path(__file__).parent / "data"
INDEX_DIR = Path(__file__).parent / "faiss_index"   # ← app\faiss_index

from langchain_community.document_loaders import (
    PyMuPDFLoader,
    TextLoader,
    Docx2txtLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

EMBED_MODEL = "BAAI/bge-small-zh-v1.5"   # 已确认与 rag_service 一致，不要动

emb = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)


def ingest_folder(folder=DEFAULT_DATA_DIR):          # ← 默认值用锚定路径
    folder = Path(folder)                            # ← 兜底，传字符串也能用
    if not folder.exists():
        print(f"数据目录不存在：{folder}")
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )

    docs = []
    for p in folder.rglob("*"):                       # ← 用局部 folder，不用相对路径
        if p.suffix == ".pdf":
            d = PyMuPDFLoader(str(p)).load()
        elif p.suffix == ".txt":
            d = TextLoader(str(p), encoding="utf-8").load()
        elif p.suffix == ".docx":
            d = Docx2txtLoader(str(p)).load()
        else:
            continue

        for x in d:
            x.metadata["source"] = p.name

        docs += splitter.split_documents(d)

    if not docs:
        print(f"未找到可入库的文档（检查目录：{folder}）")
        return

    vectorstore = FAISS.from_documents(docs, emb)
    vectorstore.save_local(str(INDEX_DIR))            # ← 关键：用 INDEX_DIR，不是 FAISS_DIR
    print(f"入库完成：共 {len(docs)} 个片段 ->", INDEX_DIR)   # ← print 也用 INDEX_DIR


def load_faiss():
    """加载已保存的 FAISS 索引，用于后续检索测试"""
    return FAISS.load_local(
        str(INDEX_DIR),                               # ← 同样改成 INDEX_DIR
        emb,
        allow_dangerous_deserialization=True,
    )


if __name__ == "__main__":
    ingest_folder()