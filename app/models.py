# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base# 导入刚才写的 database.py 里的 Base

# 1. 用户表 (user)
class User(Base):
    __tablename__ = "user"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True)
    password = Column(String(200), nullable=False)
    real_name = Column(String(50))
    phone = Column(String(20))
    email = Column(String(100))
    gender = Column(String(10))
    age = Column(Integer)
    id_card = Column(String(20))
    role = Column(String(20))
    avatar = Column(String(500))
    status = Column(String(20))
    last_login_time = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted = Column(String(1))


# 2. 系统日志表 (system_log)
class SystemLog(Base):
    __tablename__ = "system_log"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    username = Column(String(100))
    module = Column(String(50))
    action = Column(String(50))
    description = Column(Text)
    method = Column(String(10))
    request_url = Column(String(500))
    request_params = Column(Text)
    ip = Column(String(50))
    duration = Column(Integer)
    result = Column(String(20))
    error_msg = Column(Text)
    created_at = Column(DateTime, default=func.now())


# 3. 老人档案表 (elder_profile)
class ElderProfile(Base):
    __tablename__ = "elder_profile"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    room_number = Column(String(20))
    blood_type = Column(String(10))
    height = Column(Float)
    weight = Column(Float)
    allergies = Column(Text)
    medical_history = Column(Text)
    family_history = Column(Text)
    medications = Column(Text)
    disability_level = Column(String(50))
    emergency_contact = Column(String(100))
    emergency_phone = Column(String(20))
    dietary_restrictions = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted = Column(String(1))

    # 关联关系
    # 关联关系
    user = relationship("User", backref="elder_profile")

    appointments = relationship(
        "CheckupAppointment",
        primaryjoin="ElderProfile.user_id == CheckupAppointment.elder_user_id",
        foreign_keys="CheckupAppointment.elder_user_id",
        viewonly=True,
    )

    reports = relationship(
        "CheckupReport",
        primaryjoin="ElderProfile.user_id == CheckupReport.elder_user_id",
        foreign_keys="CheckupReport.elder_user_id",
        viewonly=True,
    )


# 4. 家属绑定表 (family_binding)
class FamilyBinding(Base):
    __tablename__ = "family_binding"
    id = Column(Integer, primary_key=True, index=True)
    family_user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    elder_user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    relationship = Column(String(50))
    is_primary = Column(String(1))
    bind_status = Column(String(20))
    bind_time = Column(DateTime)
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    deleted = Column(String(1))


# 5. 体检套餐表 (checkup_package)
class CheckupPackage(Base):
    __tablename__ = "checkup_package"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    price = Column(Float)
    duration_minutes = Column(Integer)
    target_group = Column(String(100))
    image = Column(String(500))
    is_active = Column(String(1))
    sort_order = Column(Integer)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted = Column(String(1))


# 6. 体检项目表 (checkup_item)
class CheckupItem(Base):
    __tablename__ = "checkup_item"
    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("checkup_package.id"), nullable=False)
    name = Column(String(100), nullable=False)
    category = Column(String(50))
    description = Column(Text)
    normal_range = Column(String(100))
    unit = Column(String(20))
    sort_order = Column(Integer)
    is_required = Column(String(1))
    created_at = Column(DateTime, default=func.now())
    deleted = Column(String(1))


# 7. 体检预约表 (checkup_appointment)
class CheckupAppointment(Base):
    __tablename__ = "checkup_appointment"
    id = Column(Integer, primary_key=True, index=True)
    appointment_no = Column(String(50), unique=True)
    elder_user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    package_id = Column(Integer, ForeignKey("checkup_package.id"), nullable=False)
    booked_by = Column(Integer)
    appointment_date = Column(DateTime, nullable=False)
    time_slot = Column(String(50))
    status = Column(String(20))
    notes = Column(Text)
    cancelled_reason = Column(Text)
    cancelled_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted = Column(String(1))

    # 关联关系
    elder = relationship(
        "ElderProfile",
        primaryjoin="CheckupAppointment.elder_user_id == ElderProfile.user_id",
        foreign_keys="[CheckupAppointment.elder_user_id]",
        viewonly=True,
    )


# 8. 体检执行表 (checkup_execution)
class CheckupExecution(Base):
    __tablename__ = "checkup_execution"
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("checkup_appointment.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("checkup_item.id"), nullable=False)
    status = Column(String(20))
    assigned_to = Column(Integer)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# 9. 体检结果表 (checkup_result)
class CheckupResult(Base):
    __tablename__ = "checkup_result"
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("checkup_execution.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("checkup_item.id"), nullable=False)
    result_value = Column(String(50))
    result_text = Column(Text)
    is_abnormal = Column(String(1))
    abnormal_flag = Column(String(10))
    reference_range = Column(String(100))
    remarks = Column(Text)
    operator_id = Column(Integer)
    recorded_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# 10. 体检报告表 (checkup_report)
class CheckupReport(Base):
    __tablename__ = "checkup_report"
    id = Column(Integer, primary_key=True, index=True)
    report_no = Column(String(50), unique=True)
    appointment_id = Column(Integer, ForeignKey("checkup_appointment.id"), nullable=False)
    elder_user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    overall_assessment = Column(Text)
    health_score = Column(Float)
    risk_level = Column(String(20))
    summary = Column(Text)
    status = Column(String(20))
    generated_by = Column(Integer)
    generated_at = Column(DateTime, default=func.now())
    published_at = Column(DateTime)
    report_file_url = Column(String(500))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    deleted = Column(String(1))

    # 关联关系
    elder = relationship(
        "ElderProfile",
        back_populates="reports",
        primaryjoin="CheckupReport.elder_user_id == ElderProfile.user_id",
        foreign_keys="[CheckupReport.elder_user_id]",
    )


# 11. 健康建议表 (health_advice)
class HealthAdvice(Base):
    __tablename__ = "health_advice"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("checkup_report.id"), nullable=False)
    category = Column(String(50))
    title = Column(String(100))
    content = Column(Text)
    priority = Column(String(20))
    follow_up_date = Column(DateTime)
    created_at = Column(DateTime, default=func.now())