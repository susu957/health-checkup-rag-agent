from datetime import datetime
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models import User, ElderProfile, CheckupAppointment, CheckupReport
from app.database import SessionLocal


def _get_db() -> Session:
    return SessionLocal()


def get_elderly_profile(elderly_id: int, db: Session | None = None) -> dict | None:
    should_close = False
    if db is None:
        db = _get_db()
        should_close = True
    try:
        user = db.query(User).filter(User.id == elderly_id).first()
        if not user:
            return None

        profile = db.query(ElderProfile).filter(ElderProfile.user_id == elderly_id).first()

        profile_data = {}
        if profile:
            profile_data = {
                "room_number": profile.room_number,
                "blood_type": profile.blood_type,
                "height": profile.height,
                "weight": profile.weight,
                "allergies": profile.allergies,
                "medical_history": profile.medical_history,
                "family_history": profile.family_history,
                "medications": profile.medications,
                "disability_level": profile.disability_level,
                "emergency_contact": profile.emergency_contact,
                "emergency_phone": profile.emergency_phone,
                "dietary_restrictions": profile.dietary_restrictions,
            }

        return {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "gender": user.gender,
            "age": user.age,
            "phone": user.phone,
            "id_card": user.id_card,
            **profile_data,
        }
    finally:
        if should_close:
            db.close()


def get_appointments_by_date(appointment_date: str, db: Session | None = None) -> list[dict]:
    should_close = False
    if db is None:
        db = _get_db()
        should_close = True
    try:
        rows = (
            db.query(CheckupAppointment, User.real_name)
            .join(User, CheckupAppointment.elder_user_id == User.id)
            .filter(CheckupAppointment.appointment_date.like(f"{appointment_date}%"))
            .all()
        )

        result = []
        for appt, real_name in rows:
            result.append({
                "id": appt.id,
                "appointment_no": appt.appointment_no,
                "elder_user_id": appt.elder_user_id,
                "elder_name": real_name,
                "appointment_date": str(appt.appointment_date),
                "time_slot": appt.time_slot,
                "package_id": appt.package_id,
                "status": appt.status,
                "notes": appt.notes,
            })
        return result
    finally:
        if should_close:
            db.close()


def create_report(report_data: dict, db: Session | None = None) -> dict:
    should_close = False
    if db is None:
        db = _get_db()
        should_close = True
    try:
        appointment_id = report_data["appointment_id"]
        elder_user_id = report_data["elder_user_id"]

        existing = (
            db.query(CheckupReport)
            .filter_by(appointment_id=appointment_id)
            .first()
        )

        if existing:
            existing.report_no = report_data.get("report_no", existing.report_no)
            existing.overall_assessment = report_data.get("overall_assessment", existing.overall_assessment)
            existing.health_score = report_data.get("health_score", existing.health_score)
            existing.risk_level = report_data.get("risk_level", existing.risk_level)
            existing.summary = report_data.get("summary", existing.summary)
            existing.status = report_data.get("status", existing.status)
            existing.report_file_url = report_data.get("report_file_url", existing.report_file_url)

            db.commit()
            db.refresh(existing)

            return {
                "id": existing.id,
                "report_no": existing.report_no,
                "elder_user_id": existing.elder_user_id,
                "summary": existing.summary,
                "status": existing.status,
            }

        report = CheckupReport(
            report_no=report_data.get("report_no"),
            appointment_id=appointment_id,
            elder_user_id=elder_user_id,
            overall_assessment=report_data.get("overall_assessment"),
            health_score=report_data.get("health_score"),
            risk_level=report_data.get("risk_level"),
            summary=report_data.get("summary"),
            status=report_data.get("status", "draft"),
            report_file_url=report_data.get("report_file_url"),
        )

        db.add(report)
        db.commit()
        db.refresh(report)

        return {
            "id": report.id,
            "report_no": report.report_no,
            "elder_user_id": report.elder_user_id,
            "summary": report.summary,
            "status": report.status,
        }
    finally:
        if should_close:
            db.close()


def create_appointment(appointment_data: dict, db: Session | None = None) -> dict:
    should_close = False
    if db is None:
        db = _get_db()
        should_close = True
    try:
        appointment_no = f"APT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:4].upper()}"

        appt_date_str = appointment_data.get("appointment_date", "")
        if isinstance(appt_date_str, str):
            appointment_date = datetime.strptime(appt_date_str, "%Y-%m-%d")
        else:
            appointment_date = appt_date_str

        appt = CheckupAppointment(
            appointment_no=appointment_no,
            elder_user_id=appointment_data["elder_user_id"],
            package_id=appointment_data["package_id"],
            booked_by=appointment_data.get("booked_by") or appointment_data["elder_user_id"],
            appointment_date=appointment_date,
            time_slot=appointment_data.get("time_slot"),
            status=appointment_data.get("status", "booked"),
            notes=appointment_data.get("notes"),
        )

        db.add(appt)
        db.commit()
        db.refresh(appt)

        return {
            "id": appt.id,
            "appointment_no": appt.appointment_no,
            "elder_user_id": appt.elder_user_id,
            "appointment_date": str(appt.appointment_date),
            "time_slot": appt.time_slot,
            "status": appt.status,
        }
    finally:
        if should_close:
            db.close()


def get_latest_report(elder_user_id: int, db: Session | None = None) -> dict | None:
    should_close = False
    if db is None:
        db = _get_db()
        should_close = True
    try:
        report = (
            db.query(CheckupReport)
            .filter_by(elder_user_id=elder_user_id, deleted=None)
            .order_by(CheckupReport.generated_at.desc(), CheckupReport.id.desc())
            .first()
        )

        if not report:
            return None

        return {
            "id": report.id,
            "report_no": report.report_no,
            "elder_user_id": report.elder_user_id,
            "overall_assessment": report.overall_assessment,
            "health_score": report.health_score,
            "risk_level": report.risk_level,
            "summary": report.summary,
            "status": report.status,
            "generated_at": str(report.generated_at) if report.generated_at else None,
            "published_at": str(report.published_at) if report.published_at else None,
            "report_file_url": report.report_file_url,
        }
    finally:
        if should_close:
            db.close()