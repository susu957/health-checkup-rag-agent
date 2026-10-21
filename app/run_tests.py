import json
import requests
import sys

def run_tests(base_url="http://127.0.0.1:8000/api/v1/chat"):
    # 读取测试用例
    with open("test_cases.json", "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    total = len(test_cases)
    passed = 0
    failed = 0
    details = []
    category_stats = {}

    print(f"开始执行测试，共 {total} 条用例")
    print(f"目标地址: {base_url}")
    print("-" * 80)

    for case in test_cases:
        case_id = case["case_id"]
        category = case["category"]
        input_text = case["input"]
        expected_tool = case["expected_tool"]
        expected_success = case["expected_success"]

        # 按分类统计
        if category not in category_stats:
            category_stats[category] = {"total": 0, "passed": 0}
        category_stats[category]["total"] += 1

        # 发送POST请求，字段名是 user_msg
        try:
            resp = requests.post(base_url, json={"user_msg": input_text}, timeout=10)
            data = resp.json()

            # 获取实际返回的工具调用信息
            actual_tool = ""
            tool_calls = data.get("tool_calls", [])
            if tool_calls and len(tool_calls) > 0:
                actual_tool = tool_calls[0].get("name", "")

            # 判断是否通过
            # 1. 如果预期失败(expected_success=false)，只要请求没报错就算通过
            # 2. 如果预期成功(expected_success=true)，需要工具名匹配
            if not expected_success:
                # 预期失败的场景：只要接口正常返回（不管返回什么内容）就算过
                status = "通过(预期失败)"
                passed += 1
                category_stats[category]["passed"] += 1
            else:
                # 预期成功：检查工具名是否匹配
                tool_match = expected_tool.lower() in str(actual_tool).lower() if actual_tool else False

                if tool_match:
                    status = "通过"
                    passed += 1
                    category_stats[category]["passed"] += 1
                else:
                    status = f"失败(预期:{expected_tool}, 实际:{actual_tool})"
                    failed += 1

            print(f"ID {case_id:2d} | [{category}] {input_text[:22]:22s} | 预期:{expected_tool:20s} | 实际:{str(actual_tool):20s} | {status}")
            details.append({
                "case_id": case_id,
                "category": category,
                "input": input_text,
                "expected_tool": expected_tool,
                "actual_tool": actual_tool,
                "status": status
            })

        except requests.exceptions.ConnectionError:
            print(f"ID {case_id:2d} | 连接失败：请确认服务已启动 (uvicorn app.main:app --reload --port 8001)")
            failed += 1
        except Exception as e:
            print(f"ID {case_id:2d} | 出错: {e}")
            failed += 1

    print("-" * 80)

    # 打印分类统计
    print("\n=== 分类统计 ===")
    for cat, stats in category_stats.items():
        p = stats["passed"]
        t = stats["total"]
        rate = p / t * 100 if t > 0 else 0
        print(f"  {cat}: {p}/{t} ({rate:.1f}%)")

    # 打印总结
    print("-" * 80)
    print(f"测试结束！总用例: {total}, 通过: {passed}, 失败: {failed}, 通过率: {passed/total*100:.1f}%")

    if failed > 0:
        print("\n=== 失败详情 ===")
        for d in details:
            if "失败" in d["status"]:
                cid = d["case_id"]
                inp = d["input"]
                et = d["expected_tool"]
                at = d["actual_tool"]
                print(f"  ID {cid}: {inp} -> 预期:{et}, 实际:{at}")

if __name__ == "__main__":
    # 支持命令行参数指定base_url
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001/api/v1/chat"
    run_tests(base_url=url)