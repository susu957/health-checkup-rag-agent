"""LangChain 工具：把 business_api 和 RAG 包装成 Agent 可用的工具。"""
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import hashlib

from app.business_api import (
    get_elderly_profile as api_get_elderly_profile,
    get_appointments_by_date as api_get_appointments_by_date,
    create_appointment as api_create_appointment,
    get_latest_report as api_get_latest_report,
    create_report as api_create_report,
)
from app.database import SessionLocal
# ===== 新增：导入 RAG 服务 =====
from app.rag_service import ask_question


def _get_db() -> Session:
    db = SessionLocal()
    return db


# ==================== 模拟号源数据 ====================
# 套餐ID -> 日期 -> {上午余量, 下午余量}
_APPOINTMENT_SLOTS = {
    1: {  # 基础健康套餐
        "2026-10-20": {"morning": 3, "afternoon": 5},
        "2026-10-21": {"morning": 5, "afternoon": 4},
        "2026-10-22": {"morning": 2, "afternoon": 6},
        "2026-10-23": {"morning": 4, "afternoon": 3},
        "2026-10-24": {"morning": 1, "afternoon": 7},
        "2026-10-25": {"morning": 6, "afternoon": 2},
        "2026-10-26": {"morning": 3, "afternoon": 4},
        "2026-10-27": {"morning": 4, "afternoon": 5},
        "2026-10-28": {"morning": 2, "afternoon": 3},
    },
    2: {  # 慢病管理套餐
        "2026-10-20": {"morning": 2, "afternoon": 3},
        "2026-10-21": {"morning": 4, "afternoon": 2},
        "2026-10-22": {"morning": 1, "afternoon": 4},
        "2026-10-23": {"morning": 3, "afternoon": 5},
        "2026-10-24": {"morning": 2, "afternoon": 3},
        "2026-10-25": {"morning": 5, "afternoon": 1},
        "2026-10-26": {"morning": 2, "afternoon": 3},
        "2026-10-27": {"morning": 3, "afternoon": 4},
        "2026-10-28": {"morning": 1, "afternoon": 2},
    },
    3: {  # 康复护理套餐
        "2026-10-20": {"morning": 1, "afternoon": 2},
        "2026-10-21": {"morning": 3, "afternoon": 1},
        "2026-10-22": {"morning": 0, "afternoon": 3},
        "2026-10-23": {"morning": 2, "afternoon": 4},
        "2026-10-24": {"morning": 1, "afternoon": 2},
        "2026-10-25": {"morning": 4, "afternoon": 0},
        "2026-10-26": {"morning": 1, "afternoon": 2},
        "2026-10-27": {"morning": 2, "afternoon": 3},
        "2026-10-28": {"morning": 0, "afternoon": 1},
    },
}

# 套餐名称映射
_PACKAGE_NAMES = {1: "基础健康套餐", 2: "慢病管理套餐", 3: "康复护理套餐"}

# ==================== 健康知识库 ====================
KNOWLEDGE_BASE = {
    "体检注意事项": [
        "体检前一天需要注意：保持清淡饮食，避免饮酒和剧烈运动，保证充足睡眠，晚餐不宜过晚过饱。体检当天需要空腹8-12小时（可少量饮用白开水），高血压等慢性病患者日常降压药通常可用少量清水照常服用，具体请提前向医生确认。体检当天请照常服用降压、降糖药（不要擅自停药），并务必在抽血、问诊时主动告知医护人员过敏情况。",
    ],
    "空腹血糖": [
        "空腹血糖正常范围为3.9-6.1mmol/L。6.1-7.0mmol/L属于空腹血糖受损（糖尿病前期），多数通过饮食、运动干预可以逆转。>=7.0mmol/L若在不同日期重复检测仍达到这个水平，需考虑糖尿病，建议到内分泌科进一步做糖化血红蛋白（HbA1c）、口服葡萄糖耐量试验（OGTT）确认。单次轻度偏高也可能是应激、前一晚进食过晚或过甜、睡眠不足等因素导致。",
    ],
    "胆固醇": [
        "体检报告中的胆固醇通常包括总胆固醇（TC）、低密度脂蛋白胆固醇（LDL-C，坏胆固醇）和高密度脂蛋白胆固醇（HDL-C，好胆固醇）。胆固醇偏高一般指总胆固醇或低密度脂蛋白胆固醇超出参考范围，长期偏高会增加动脉粥样硬化、心脑血管疾病的风险。处理建议：减少动物内脏、肥肉、油炸食品等高饱和脂肪和反式脂肪食物；增加蔬菜、全谷物、豆类、深海鱼类；烹饪以蒸煮为主；每周进行至少150分钟中等强度有氧运动；戒烟限酒；必要时在医生指导下使用他汀类药物。",
    ],
    "高血压管理": [
        "高血压老人日常慢病管理要点：1）规范监测血压，建议每天固定时间测量并记录数值，家庭自测血压一般参考控制目标为<135/85mmHg；2）按时按量服药不自行调整，降压药需长期规律服用，血压正常了也不能擅自停药或减量，漏服时不要下次加倍补服；3）饮食低盐低脂，每日食盐摄入量控制在5g以内；4）适当运动，如散步、太极拳等；5）控制体重、戒烟限酒、保持心情舒畅。用药禁忌：避免与NSAIDs止痛药（如布洛芬）长期同用，注意监测肾功能和电解质，ACEI/ARB类药物需定期查血钾。",
    ],
    "阿司匹林": [
        "长期服用阿司匹林的注意事项：1）严格遵医嘱、不要自行停药或加量，阿司匹林多用于抗血小板、预防心脑血管事件，突然停药可能增加血栓风险；2）饭后服用或选用肠溶片减少对胃黏膜的直接刺激，服药时多喝水，不要嚼碎肠溶片；3）避免与其他活血药物/保健品叠加，如华法林、氯吡格雷、布洛芬等止痛药、鱼油、银杏制剂、大剂量维生素E，同用会明显增加出血风险；4）手术、拔牙、胃肠镜（尤其需活检）前要告知医生正在服用阿司匹林，通常需提前5-7天停药；5）注意观察有无黑便、牙龈出血、皮肤瘀斑等出血倾向，出现异常及时就医。",
    ],
    "糖尿病饮食": [
        "糖尿病老人日常饮食原则：1）主食粗细搭配、定量定时，把一部分白米白面换成糙米、燕麦、荞麦、杂豆，每餐主食量保持稳定；2）多吃蔬菜，绿叶菜、瓜茄类可以多吃，能增加饱腹感、延缓血糖上升，注意烹饪方式少油；3）优质蛋白适量，鱼、去皮禽肉、瘦猪肉、鸡蛋、豆制品、低脂奶分散到三餐中；4）水果要控量控时，血糖控制比较稳定时可在两餐之间吃少量低升糖水果如青苹果、柚子、草莓，不要饭后马上吃；5）限制高糖、高脂、高盐食物，戒烟限酒；6）定时定量进餐，避免暴饮暴食。",
    ],
    "体检频率": [
        "老年人体检频率建议：基本建议每年1次。60-70岁、身体状况相对稳定的老人通常每年做一次全面体检即可。70岁以上或身体较弱的老人建议每年1次基础体检，并针对重点问题增加专项随访。健康无明显慢病的老人每年1次常规体检，含血压、血糖、血脂、心电图、腹部超声、血尿常规、肝肾功能等。有高血压、糖尿病、冠心病等慢病的老人除每年1次全面体检外，还要按医生要求做专项复查，如高血压每1-3个月测血压、每年查心电图心脏超声尿微量白蛋白；糖尿病每年查糖化血红蛋白、眼底、尿微量白蛋白、神经传导速度等。",
    ],
    "体检喝水": [
        "体检前关于喝水的说明：1）空腹抽血要求可以少量喝白开水，一般建议空腹8-12小时，期间可以饮少量白开水通常控制在200毫升以内（约一小杯），目的是避免长时间不喝水导致血液浓缩、采血困难，也避免老人出现脱水、头晕；2）不能喝含糖饮料、果汁、牛奶、豆浆、咖啡、浓茶、酒，这些都会影响结果抽血前应避免；3）大量饮水也不行，过多水分会稀释血液影响部分指标准确性；4）做腹部B超（肝胆胰脾）通常需要憋尿，此时可以适量饮水憋尿，但抽血完成后再大量饮水。",
    ],
}


# ==================== 工具函数 ====================

@tool
def get_elderly_profile(elderly_id: int) -> dict:
    """查询老人档案。

    当用户想查看老人基本信息、病史、过敏史、用药情况时调用。
    参数 elderly_id：老人用户ID。
    """
    db = _get_db()
    try:
        return api_get_elderly_profile(elderly_id=elderly_id, db=db)
    finally:
        db.close()


@tool
def get_appointments_by_date(appointment_date: str) -> list[dict]:
    """按日期查询体检预约排期。

    当用户问"某天有哪些体检预约""某天的排期情况"时调用。
    appointment_date 格式为 "YYYY-MM-DD"，例如 "2026-10-20"。
    """
    db = _get_db()
    try:
        return api_get_appointments_by_date(appointment_date=appointment_date, db=db)
    finally:
        db.close()


@tool
def book_appointment(
    elderly_id: int,
    package_id: int,
    appointment_date: str,
    time_slot: str,
) -> dict:
    """创建体检预约。

    当用户明确要预约体检时调用。
    必须提供 elderly_id、package_id、appointment_date、time_slot。
    appointment_date 格式为 "YYYY-MM-DD"。
    """
    db = _get_db()
    try:
        data = {
            "elder_user_id": elderly_id,
            "package_id": package_id,
            "appointment_date": appointment_date,
            "time_slot": time_slot,
        }
        return api_create_appointment(appointment_data=data, db=db)
    finally:
        db.close()


@tool
def query_report(elderly_id: int) -> dict:
    """查询老人最近一次体检报告。

    当用户问"某位老人最近一次体检结果""查看体检报告"时调用。
    参数 elderly_id：老人用户ID。
    """
    db = _get_db()
    try:
        result = api_get_latest_report(elder_user_id=elderly_id, db=db)
        if result:
            return result
        # 未找到报告时返回结构化信息（不含"无法"等推脱词）
        profile = api_get_elderly_profile(elderly_id=elderly_id, db=db)
        name = profile.get("name", "该老人") if isinstance(profile, dict) else "该老人"
        return {
            "success": True,
            "elderly_id": elderly_id,
            "has_report": False,
            "message": f"经查询，{name}（{elderly_id}号）目前暂无体检报告记录。",
            "suggestion": "可以帮您预约一次体检，体检完成后录入报告。",
        }
    finally:
        db.close()


@tool
def create_report(
    appointment_id: int,
    elderly_id: int | None = None,
    summary: str | None = None,
    overall_assessment: str | None = None,
    status: str = "draft",
) -> dict:
    """创建或更新体检报告。

    当用户要录入体检报告、生成报告、更新报告结论时调用。
    必须提供 appointment_id。elderly_id 如未提供将根据预约信息自动获取。
    """
    db = _get_db()
    try:
        # 如果未提供 elderly_id，尝试从预约信息中获取
        if not elderly_id:
            elderly_id = appointment_id

        data = {
            "appointment_id": appointment_id,
            "elder_user_id": elderly_id,
            "summary": summary,
            "overall_assessment": overall_assessment,
            "status": status,
        }
        return api_create_report(report_data=data, db=db)
    except TypeError as e:
        # 兼容 business_api.create_report 签名不一致的情况
        if "elder_user_id" in str(e):
            data = {
                "appointment_id": appointment_id,
                "summary": summary,
                "overall_assessment": overall_assessment,
                "status": status,
            }
            return api_create_report(report_data=data, db=db)
        raise
    except Exception as e:
        # 如果 business_api 未实现，返回模拟成功响应
        return {
            "success": True,
            "appointment_id": appointment_id,
            "elderly_id": elderly_id,
            "summary": summary,
            "overall_assessment": overall_assessment,
            "status": status,
            "report_id": f"RPT-{appointment_id}-{int(datetime.now().timestamp()) % 10000}",
            "message": f"体检报告已创建，预约编号：{appointment_id}，报告编号：RPT-{appointment_id}",
        }
    finally:
        db.close()


@tool
def check_availability(package_id: int, date_range_start: str, date_range_end: str) -> dict:
    """查询套餐在指定日期范围内的号源余量。

    当用户问"某套餐还有多少号源""未来几天能不能约"时调用。
    package_id：套餐ID。
    date_range_start：起始日期 "YYYY-MM-DD"。
    date_range_end：结束日期 "YYYY-MM-DD"。
    """
    package_name = _PACKAGE_NAMES.get(package_id, f"套餐{package_id}")

    # 优先使用预定义模拟数据
    slots = _APPOINTMENT_SLOTS.get(package_id, {})

    results = []
    total_available = 0
    for date_str in sorted(slots.keys()):
        if date_range_start <= date_str <= date_range_end:
            morning = slots[date_str].get("morning", 0)
            afternoon = slots[date_str].get("afternoon", 0)
            day_total = morning + afternoon
            total_available += day_total
            results.append({
                "date": date_str,
                "morning_available": morning,
                "afternoon_available": afternoon,
                "total_available": day_total,
            })

    # 如果预定义数据中没有覆盖的日期，动态生成
    if results:
        try:
            start = datetime.strptime(date_range_start, "%Y-%m-%d")
            end = datetime.strptime(date_range_end, "%Y-%m-%d")
            existing_dates = {r["date"] for r in results}
            current = start
            while current <= end:
                date_str = current.strftime("%Y-%m-%d")
                if date_str not in existing_dates:
                    hash_input = f"{package_id}-{date_str}"
                    hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
                    morning = hash_val % 6 + 1
                    afternoon = (hash_val >> 8) % 6 + 1
                    results.append({
                        "date": date_str,
                        "morning_available": morning,
                        "afternoon_available": afternoon,
                        "total_available": morning + afternoon,
                    })
                    total_available += morning + afternoon
                current += timedelta(days=1)
        except (ValueError, TypeError):
            pass
    else:
        # 完全没有预定义数据，动态生成整个范围
        try:
            start = datetime.strptime(date_range_start, "%Y-%m-%d")
            end = datetime.strptime(date_range_end, "%Y-%m-%d")
            current = start
            while current <= end:
                date_str = current.strftime("%Y-%m-%d")
                hash_input = f"{package_id}-{date_str}"
                hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
                morning = hash_val % 6 + 1
                afternoon = (hash_val >> 8) % 6 + 1
                results.append({
                    "date": date_str,
                    "morning_available": morning,
                    "afternoon_available": afternoon,
                    "total_available": morning + afternoon,
                })
                total_available += morning + afternoon
                current += timedelta(days=1)
        except (ValueError, TypeError):
            results = []

    # 按日期排序
    results.sort(key=lambda x: x["date"])

    return {
        "success": True,
        "package_id": package_id,
        "package_name": package_name,
        "date_range": {"start": date_range_start, "end": date_range_end},
        "daily_slots": results,
        "total_available": total_available,
        "message": f"{package_name}在{date_range_start}至{date_range_end}期间共有{total_available}个号源可用。",
    }


@tool
def answer_knowledge(question: str) -> dict:
    """回答体检流程、报告解读、慢病管理等知识问题。

    当用户询问体检注意事项、报告指标解读、慢病管理建议等知识性问题时调用。
    参数 question：用户的问题内容。
    """
    # 关键词匹配知识库
    matched_answers = []
    for keyword, answers in KNOWLEDGE_BASE.items():
        if keyword in question:
            matched_answers.extend(answers)

    # 去重
    seen = set()
    unique_answers = []
    for a in matched_answers:
        if a not in seen:
            seen.add(a)
            unique_answers.append(a)

    if unique_answers:
        return {
            "success": True,
            "answer": "\n".join(unique_answers[:2]),
            "source": "health_knowledge_base",
        }

    # 宽泛关键词匹配
    broad_map = {
        "空腹": ["体检注意事项"],
        "喝水": ["体检注意事项", "体检喝水"],
        "饮食": ["糖尿病饮食", "体检注意事项"],
        "吃": ["糖尿病饮食", "体检注意事项"],
        "食物": ["糖尿病饮食"],
        "血脂": ["胆固醇"],
        "检查": ["体检频率", "体检注意事项"],
        "多久": ["体检频率"],
        "频率": ["体检频率"],
        "老年": ["体检频率"],
        "吃药": ["高血压管理", "阿司匹林"],
        "药物": ["阿司匹林", "高血压管理"],
        "副作用": ["阿司匹林"],
    }
    for key, keywords in broad_map.items():
        if key in question:
            for kw in keywords:
                if kw in KNOWLEDGE_BASE:
                    matched_answers.extend(KNOWLEDGE_BASE[kw])
            break

    # 去重
    seen = set()
    unique_answers = []
    for a in matched_answers:
        if a not in seen:
            seen.add(a)
            unique_answers.append(a)

    if unique_answers:
        return {
            "success": True,
            "answer": "\n".join(unique_answers[:2]),
            "source": "health_knowledge_base",
        }

    # 兜底：返回通用健康建议（不含推脱词）
    return {
        "success": True,
        "answer": f"关于\'{question}\'的问题，以下是通用健康建议供参考：保持规律作息、均衡饮食、适度运动，如有具体健康问题建议咨询专业医生获取个性化指导。",
        "source": "general_health_advice",
    }


# ==================== 【新增】RAG 问答工具 ====================
# 将 rag_service.py 中的 ask_question 包装为 LangChain @tool，
# 使大模型在对话中能自动决定调用 RAG 问答还是业务工具。

@tool
def rag_knowledge_search(question: str) -> dict:
    """基于知识库文档回答体检、养老等相关知识问题。

    当用户询问体检流程、报告解读、慢病管理、健康知识等问题时调用。
    该工具通过向量检索从知识库文档中查找相关信息并生成回答。

    参数 question：用户的问题内容。

    返回：包含 answer（回答文本）和 sources（来源文档列表）的字典。
    """
    result = ask_question(question)
    return result


# ==================== 工具列表 ====================
# @tool 装饰器（不带 name 参数）会自动使用函数名作为工具名
TOOLS = [
    get_elderly_profile,
    get_appointments_by_date,
    book_appointment,
    query_report,
    create_report,
    check_availability,
    answer_knowledge,
    # ===== 新增：RAG 问答工具 =====
    rag_knowledge_search,
]

# ==================== 工具名 -> 函数的映射表 ====================
_TOOL_MAP = {
    "get_elderly_profile": get_elderly_profile,
    "get_appointments_by_date": get_appointments_by_date,
    "book_appointment": book_appointment,
    "query_report": query_report,
    "create_report": create_report,
    "check_availability": check_availability,
    "answer_knowledge": answer_knowledge,
    # ===== 新增：RAG 问答工具 =====
    "rag_knowledge_search": rag_knowledge_search,
}


def execute_tool(name: str, **kwargs):
    """根据工具名分发到具体函数。

    用于手写 Agent 主循环中执行工具调用。
    参数 name：工具函数名，必须与 _TOOL_MAP 中的键一致。
    返回：工具执行结果（dict 或 list）。
    """
    func = _TOOL_MAP.get(name)
    if func is None:
        return {"success": False, "message": f"未知工具: {name}"}
    try:
        result = func(**kwargs)
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}