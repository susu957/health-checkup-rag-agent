import requests

BASE = "http://127.0.0.1:8080"

# 1. 先登录拿 token（账号密码用你数据库里真实的那组，比如 admin / 123456）
login_url = BASE + "/api/auth/login"   # 这个路径以 Knife4j「用户管理-登录」详情页显示的为准
payload = {"username": "admin", "password": "123456"}
r = requests.post(login_url, json=payload, timeout=5)
print("登录:", r.status_code, r.text[:200])

data = r.json()
# token 可能在 data["token"] 或 data["data"]["token"]，按实际返回取
token = data.get("token") or data.get("data", {}).get("token")
print("token:", token)

# 2. 带上 token 再调业务接口
headers = {"Authorization": "Bearer " + token}   # 若项目不加 Bearer，就改成 {"Authorization": token}
for path in ["/api/appointment/slots", "/api/report/latest"]:
    r = requests.get(BASE + path, headers=headers, timeout=5)
    print(path, r.status_code, r.text[:200])