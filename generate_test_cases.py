import json
from pathlib import Path

test_cases = [
    # ===== appointment：预约 / 查号 / 取消 =====
    {
        "id": 1,
        "category": "appointment",
        "user_msg": "帮老人1预约10月20号上午基础体检",
        "expected_tool": "book_appointment",
    },
    {
        "id": 2,
        "category": "appointment",
        "user_msg": "给孙武约个体检",
        "expected_tool": "get_elderly_profile",
    },
    {
        "id": 3,
        "category": "appointment",
        "user_msg": "约慢病管理套餐，10月21号上午",
        "expected_tool": "book_appointment",
    },
    {
        "id": 4,
        "category": "appointment",
        "user_msg": "帮我看看10月22号上午还有没有号",
        "expected_tool": "check_availability",
    },
    {
        "id": 5,
        "category": "appointment",
        "user_msg": "取消老人3的预约",
        "expected_tool": "book_appointment",
    },
    {
        "id": 6,
        "category": "appointment",
        "user_msg": "我想约体检，但不知道选哪个套餐",
        "expected_tool": "get_elderly_profile",
    },
    {
        "id": 7,
        "category": "appointment",
        "user_msg": "老人2约10月25号下午体检",
        "expected_tool": "book_appointment",
    },
    {
        "id": 8,
        "category": "appointment",
        "user_msg": "帮我查一下10月23号下午有没有空位",
        "expected_tool": "check_availability",
    },
    {
        "id": 9,
        "category": "appointment",
        "user_msg": "老人4想改约到10月26号上午",
        "expected_tool": "book_appointment",
    },
    {
        "id": 10,
        "category": "appointment",
        "user_msg": "约一个基础体检，时间尽量安排在周末",
        "expected_tool": "book_appointment",
    },

    # ===== report：查报告 / 查指标 =====
    {
        "id": 11,
        "category": "report",
        "user_msg": "查老人1的体检报告",
        "expected_tool": "query_report",
    },
    {
        "id": 12,
        "category": "report",
        "user_msg": "孙武上次体检结果怎么样",
        "expected_tool": "query_report",
    },
    {
        "id": 13,
        "category": "report",
        "user_msg": "有没有老人5的报告",
        "expected_tool": "query_report",
    },
    {
        "id": 14,
        "category": "report",
        "user_msg": "帮我下载体检报告",
        "expected_tool": "query_report",
    },
    {
        "id": 15,
        "category": "report",
        "user_msg": "老人1最近的血糖数据",
        "expected_tool": "query_report",
    },

    # ===== knowledge：知识问答 / RAG =====
    {
        "id": 16,
        "category": "knowledge",
        "user_msg": "体检前需要空腹吗",
        "expected_tool": "answer_knowledge",
    },
    {
        "id": 17,
        "category": "knowledge",
        "user_msg": "基础体检和慢病管理套餐有什么区别",
        "expected_tool": "answer_knowledge",
    },
    {
        "id": 18,
        "category": "knowledge",
        "user_msg": "体检报告多久能出来",
        "expected_tool": "answer_knowledge",
    },
    {
        "id": 19,
        "category": "knowledge",
        "user_msg": "高血压老人体检要注意什么",
        "expected_tool": "answer_knowledge",
    },
    {
        "id": 20,
        "category": "knowledge",
        "user_msg": "可以带家属陪同体检吗",
        "expected_tool": "answer_knowledge",
    },
    {
        "id": 21,
        "category": "knowledge",
        "user_msg": "体检当天需要带什么材料",
        "expected_tool": "answer_knowledge",
    },

    # ===== profile：查档案 / 查老人信息 =====
    {
        "id": 22,
        "category": "profile",
        "user_msg": "查一下老人1的档案",
        "expected_tool": "get_elderly_profile",
    },
    {
        "id": 23,
        "category": "profile",
        "user_msg": "孙武的基本信息",
        "expected_tool": "get_elderly_profile",
    },
    {
        "id": 24,
        "category": "profile",
        "user_msg": "老人3的身份证号是多少",
        "expected_tool": "get_elderly_profile",
    },
    {
        "id": 25,
        "category": "profile",
        "user_msg": "有没有老人100的档案",
        "expected_tool": "get_elderly_profile",
    },
    {
        "id": 26,
        "category": "profile",
        "user_msg": "帮我看看老人的联系方式",
        "expected_tool": "get_elderly_profile",
    },
    {
        "id": 27,
        "category": "profile",
        "user_msg": "老人2有什么既往病史",
        "expected_tool": "get_elderly_profile",
    },
]

output = Path(__file__).resolve().parent / "test_cases.json"
output.write_text(
    json.dumps(test_cases, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print("已生成:", output)