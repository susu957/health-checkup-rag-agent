from app.business_api import (
    get_elderly_profile,
    get_appointments_by_date,
    create_report,
    create_appointment,
    get_latest_report,
)

# 这里改成你数据库里已经存在的真实 ID
ELDER_USER_ID = 1
PACKAGE_ID = 1
APPOINTMENT_DATE = "2026-10-20"
TIME_SLOT = "09:00-10:00"
CHECK_DATE = "2026-10-20"


def run():
    print("=" * 60)
    print("1. 查老人档案")
    print("=" * 60)
    result = get_elderly_profile(elderly_id=ELDER_USER_ID)
    print(result)
    print()

    print("=" * 60)
    print("2. 查某日预约情况")
    print("=" * 60)
    result = get_appointments_by_date(appointment_date=CHECK_DATE)
    print(result)
    print()

    print("=" * 60)
    print("3. 查询最新报告")
    print("=" * 60)
    result = get_latest_report(elder_user_id=ELDER_USER_ID)
    print(result)
    print()

    print("=" * 60)
    print("4. 创建预约")
    print("=" * 60)
    result = create_appointment(
        appointment_data={
            "elder_user_id": ELDER_USER_ID,
            "package_id": PACKAGE_ID,
            "appointment_date": APPOINTMENT_DATE,
            "time_slot": TIME_SLOT,
        },
    )
    print(result)
    print()

    print("=" * 60)
    print("5. 创建报告")
    print("=" * 60)
    result = create_report(
        report_data={
            "report_no": "RPT-TEST-002",  # 加上这一行
            "appointment_id": 10,  # 用上面第4步返回的id
            "elder_user_id": ELDER_USER_ID,
            "summary": "测试报告：各项指标基本正常，建议定期复查。",
            "status": "published",
        },
    )
    print(result)
    print()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    run()