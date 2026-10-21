import sys
sys.path.insert(0, '.')
from app.rag_service import ask_question

# 测试1：问 data 目录下文档里应该有的问题
result = ask_question("体检前需要空腹多久")
print("答案:", result["answer"][:300])
print("来源:", result["sources"])

# 测试2：问文档里肯定没有的问题（检验不幻觉）
result2 = ask_question("2077年奥运会在哪里举办")
print("答案2:", result2["answer"])