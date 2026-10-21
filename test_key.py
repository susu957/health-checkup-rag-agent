import requests, json

r = requests.post(
    "http://127.0.0.1:8000/rag/ask",
    json={"questions": ["体检前需要空腹多久", "高血压饮食注意什么", "养老院入住费用多少"]},
    timeout=30,
)
print("状态码:", r.status_code)
print(json.dumps(r.json(), ensure_ascii=False, indent=2))