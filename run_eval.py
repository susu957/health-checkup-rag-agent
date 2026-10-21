import json
import time
from pathlib import Path

# ============ 配置区 ============
BASE_URL = "http://127.0.0.1:8000"
CHAT_URL = f"{BASE_URL}/api/v1/chat"
INPUT_FILE = Path(__file__).resolve().parent / "test_cases.json"
OUTPUT_FILE = Path(__file__).resolve().parent / "eval_results.json"
TIMEOUT = 30  # 秒
MAX_RETRIES = 1  # 失败重试次数
RETRY_DELAY = 2  # 重试间隔（秒）


def load_test_cases():
    """加载测试用例，支持多种字段名兼容"""
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)
    normalized = []
    for case in cases:
        question = (
            case.get("user_msg")
            or case.get("query")
            or case.get("question")
            or case.get("input")
            or case.get("prompt")
            or ""
        )
        expected = case.get("expected_tool") or case.get("intent") or case.get("expected_answer") or ""
        normalized.append({
            "id": case.get("id", len(normalized) + 1),
            "question": question,
            "expected": expected,
            "raw": case,
        })
    return normalized


def call_chat(user_msg):
    """调用 /api/v1/chat，兼容各种响应结构"""
    import requests as req

    resp = req.post(
        CHAT_URL,
        json={"message": user_msg},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    # 打印原始响应（方便调试）
    print(f"         [DEBUG] 原始响应类型={type(data).__name__}, 值={str(data)[:300]}")

    # 统一提取出字符串答案
    answer = _extract_string(data)
    return {"answer": answer, "raw": data}


def _extract_string(obj):
    """递归从任意嵌套结构中提取字符串答案"""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        # 按优先级尝试常见字段名
        for key in ["answer", "response", "content", "text", "result", "data", "reply"]:
            val = obj.get(key)
            if val is not None:
                if isinstance(val, str):
                    return val
                if isinstance(val, dict):
                    # 递归深入一层
                    nested = _extract_string(val)
                    if nested:
                        return nested
                if isinstance(val, list):
                    # 如果是列表，取第一个非空元素
                    for item in val:
                        if isinstance(item, str) and item.strip():
                            return item
                        if isinstance(item, dict):
                            nested = _extract_string(item)
                            if nested:
                                return nested
        # 所有常见字段都没找到或为空，把整个dict转字符串
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, list):
        # 列表情况：拼接所有字符串元素
        parts = []
        for item in obj:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                s = _extract_string(item)
                if s:
                    parts.append(s)
        return " ".join(parts) if parts else str(obj)
    # 其他类型（int, float, bool, None等）
    return str(obj) if obj is not None else ""


def extract_answer(response: dict) -> str:
    # 你的接口返回 {"answer": {"answer": "...", "sources": [...]}}
    answer = response.get("answer")
    if isinstance(answer, dict):
        # 嵌套结构，取内层的 answer 字段
        text = answer.get("answer", "")
        return text if isinstance(text, str) else str(text)
    return str(answer) if answer else ""


def check_answer_valid(answer):
    """检查答案是否有效（非空、非占位符、非纯推脱）

    改进说明：
    - 去掉了过于激进的关键词过滤（"无法""请提供"等在很多正常回复中也会出现）
    - 改为检查真正的占位符/空回复模式
    - 保留最短长度校验防止假阳性
    """
    # 终极防御：确保 answer 是字符串
    if answer is None:
        return False
    if not isinstance(answer, str):
        answer = str(answer)
    # 过滤空字符串
    if not answer.strip():
        return False
    # 过滤掉占位符
    placeholders = ["", "null", "None", "[]", "{}", "string"]
    if answer.strip() in placeholders:
        return False
    # 过滤真正的占位/未实现提示（这些说明后端接口还没写好）
    placeholder_patterns = [
        "需根据 business_api 实际接口实现",
        "功能需根据",
        "暂未返回有效数据",
        "接口暂未实现",
    ]
    for pattern in placeholder_patterns:
        if pattern in answer:
            return False
    # 过滤过短的答案（少于10个字符认为无效）
    if len(answer.strip()) < 10:
        return False
    return True


def extract_tool_calls(resp):
    """从API响应中递归提取实际调用的工具名称列表，兼容多种响应结构"""
    # 常见字段名：tool_calls, tools, function_calls, actions
    candidates = ["tool_calls", "tools", "function_calls", "actions"]
    for key in candidates:
        val = resp.get(key)
        if val and isinstance(val, list) and len(val) > 0:
            tools = []
            for item in val:
                if isinstance(item, dict):
                    # 尝试常见字段名获取工具名
                    name = item.get("name") or item.get("function") or item.get("tool_name") or ""
                    if name:
                        tools.append(name)
                elif isinstance(item, str) and item.strip():
                    tools.append(item.strip())
            if tools:
                return tools
    # 递归搜索嵌套结构
    def _search(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in candidates and isinstance(v, list):
                    return [item.get("name", str(item)) if isinstance(item, dict) else str(item) for item in v if item]
                if isinstance(v, list):
                    result = _search(v)
                    if result:
                        return result
                if isinstance(v, dict):
                    result = _search(v)
                    if result:
                        return result
        return []
    return _search(resp)


def run_eval():
    """运行评测"""
    print("=" * 60)
    print("评测：RAG 问答链路验证 (Plan A - 三指标)")
    print(f"  接口: {CHAT_URL}")
    print(f"  测试用例: {INPUT_FILE}")
    print("=" * 60)

    # 加载测试用例
    try:
        cases = load_test_cases()
    except FileNotFoundError:
        print(f"找不到测试文件: {INPUT_FILE}")
        print("  请确保 test_cases.json 与 run_eval.py 在同一目录")
        return
    except json.JSONDecodeError as e:
        print(f"test_cases.json 格式错误: {e}")
        return

    print(f"\n共 {len(cases)} 条测试用例，开始评测...\n")

    # 执行评测
    results = []
    success_count = 0
    fail_count = 0
    empty_count = 0
    tool_match_count = 0
    tool_mismatch_count = 0
    tool_not_called = 0
    tool_mis_called = 0
    answer_valid_count = 0

    for i, case in enumerate(cases, 1):
        question = case["question"]
        case_id = case["id"]
        expected = case["expected"]
        q_display = question[:40] + "..." if len(question) > 40 else question
        print(f"  [{i:2d}/{len(cases)}] ID={case_id} 问题: {q_display}")

        # 带重试的请求
        resp = None
        last_error = None
        for retry in range(MAX_RETRIES + 1):
            try:
                resp = call_chat(question)
                last_error = None
                break
            except Exception as e:
                last_error = str(e)
                if retry < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

        if last_error:
            # 请求失败
            print(f"         请求失败: {last_error}")
            result = {
                "id": case_id,
                "question": question,
                "expected": expected,
                "status": "failed",
                "error": last_error,
                "answer": "",
                "actual_tool": "none",
                "tool_match": False,
                "answer_valid": False,
            }
            fail_count += 1
        else:
            answer = extract_answer(resp)

            # ====== 工具调用抓取和对比逻辑 ======
            actual_tool_calls = extract_tool_calls(resp.get("raw", resp))
            actual_tool = actual_tool_calls[0] if actual_tool_calls else "none"

            # 判断工具匹配
            if expected and expected.lower() != "none" and expected:
                if actual_tool != "none" and actual_tool == expected:
                    tool_match = True
                    tool_match_count += 1
                elif actual_tool == "none":
                    tool_match = False
                    tool_not_called += 1
                else:
                    tool_match = False
                    tool_mis_called += 1
            else:
                # 预期不需要调用工具
                tool_match = (actual_tool == "none")
                if tool_match:
                    tool_match_count += 1
                else:
                    tool_mismatch_count += 1

            print(f"         预期工具: {expected} | 实际工具: {actual_tool} | 匹配: {'OK' if tool_match else 'FAIL'}")
            # ====================================

            is_valid = check_answer_valid(answer)
            a_display = answer[:60] + "..." if len(answer) > 60 else answer
            if is_valid:
                print(f"         回答: {a_display}")
                answer_valid_count += 1
                success_count += 1
            else:
                print(f"         空答案或无效响应 (answer类型={type(answer).__name__}, 值={repr(answer)[:80]})")
                empty_count += 1
            result = {
                "id": case_id,
                "question": question,
                "expected": expected,
                "actual_tool": actual_tool,
                "tool_match": tool_match,
                "status": "success" if is_valid else "empty",
                "answer": answer,
                "answer_valid": is_valid,
                "raw_response": str(resp.get("raw", ""))[:200],
            }
        results.append(result)

    # 打印汇总
    total = len(cases)
    return_rate = (success_count / total * 100) if total > 0 else 0
    tool_accuracy = (tool_match_count / total * 100) if total > 0 else 0
    answer_valid_rate = (answer_valid_count / total * 100) if total > 0 else 0

    print("\n" + "=" * 60)
    print("评测结果汇总 (Plan A - 三指标)")
    print("=" * 60)
    print(f"  总用例数:       {total}")
    print(f"  成功返回:       {success_count}/{total} ({return_rate:.1f}%)")
    print(f"  空/无效答案:    {empty_count}/{total}")
    print(f"  请求失败:       {fail_count}/{total}")
    print("-" * 60)
    print("  工具调用准确率:  {} ({}%)".format(
        "OK" if tool_accuracy == 100 else "查看详情",
        tool_accuracy
    ))
    print(f"    工具匹配OK:     {tool_match_count}/{total}")
    print(f"    工具未调用:     {tool_not_called}/{total}")
    print(f"    工具误调用:     {tool_mis_called}/{total}")
    print(f"    预期无工具但调了: {tool_mismatch_count}/{total}")
    print("-" * 60)
    # ====== 三个核心指标 ======
    print("  【三个核心指标】")
    print(f"    1. 成功返回率:     {success_count}/{total} ({return_rate:.1f}%)")
    print(f"    2. 工具调用准确率: {tool_match_count}/{total} ({tool_accuracy:.1f}%)")
    print(f"    3. 答案有效性:     {answer_valid_count}/{total} ({answer_valid_rate:.1f}%)")
    print("=" * 60)

    # 打印工具不匹配的用例详情
    mismatched = [r for r in results if r.get("expected") and r.get("expected").lower() != "none" and r.get("tool_match") is False]
    if mismatched:
        print("\n工具不匹配的用例详情:")
        for r in mismatched:
            print(f"  ID={r['id']} 预期={r['expected']} 实际={r.get('actual_tool', 'N/A')} 问题={r['question'][:50]}")

    # 按类别统计
    from collections import defaultdict
    cat_stats = defaultdict(lambda: {"total": 0, "match": 0})
    for r in results:
        expected = r.get("expected", "")
        if expected:
            # 从 raw 中获取 category
            cat = r.get("raw", {}).get("category", "unknown")
            cat_stats[cat]["total"] += 1
            if r.get("tool_match") is True:
                cat_stats[cat]["match"] += 1

    if cat_stats:
        print("\n按类别工具准确率:")
        for cat, stats in cat_stats.items():
            rate = stats["match"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"  {cat}: {stats['match']}/{stats['total']} ({rate:.1f}%)")

    # 保存结果
    output = {
        "summary": {
            "total": total,
            "success": success_count,
            "return_rate": round(return_rate, 1),
            "empty": empty_count,
            "failed": fail_count,
            "tool_match_ok": tool_match_count,
            "tool_not_called": tool_not_called,
            "tool_mis_called": tool_mis_called,
            "tool_mismatch": tool_mismatch_count,
            "tool_accuracy": round(tool_accuracy, 1),
            "answer_valid": answer_valid_count,
            "answer_valid_rate": round(answer_valid_rate, 1),
        },
        "details": results,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存至: {OUTPUT_FILE}")
    print("\nPlan A 说明: 已输出完整三指标评测（成功返回率 + 工具调用准确率 + 答案有效性）。")


if __name__ == "__main__":
    run_eval()