import json
import requests

BASE_URL = "http://127.0.0.1:8000"


def diagnose(endpoint, payload):
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'=' * 60}")
    print(f"测试接口: POST {endpoint}")
    print(f"请求体: {json.dumps(payload, ensure_ascii=False)}")
    print(f"{'=' * 60}")
    try:
        resp = requests.post(url, json=payload, timeout=30)
        print(f"\n状态码: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('content-type', 'unknown')}")
        print(f"响应头: {dict(resp.headers)}")
        print(f"\n原始响应体: {resp.text[:1000]}")
        print(f"\n{'=' * 60}")

        # 尝试解析JSON
        try:
            data = resp.json()
            print(f"JSON解析成功!")
            print(f"类型: {type(data).__name__}")
            print(f"完整JSON: {json.dumps(data, ensure_ascii=False, indent=2)[:2000]}")
        except Exception as e:
            print(f"JSON解析失败: {e}")
            print(f"纯文本响应: {resp.text[:500]}")
    except requests.exceptions.ConnectionError:
        print("\n连接失败! 请确认服务正在运行 (python -m uvicorn app.main:app --reload --port 8001)")
    except requests.exceptions.Timeout:
        print("\n请求超时!")
    except Exception as e:
        print(f"\n异常: {type(e).__name__}: {e}")


# 测试 /api/v1/chat
print("开始诊断 API...")
diagnose("/api/v1/chat", {"question": "测试消息"})

# 测试 /rag/ask
diagnose("/rag/ask", {"question": "测试消息"})

print("\n诊断完成!")