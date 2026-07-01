# api/seat_routes.py - 座位预约 REST 端点（预约/签到/暂离/管理员释放）

import os, uuid, asyncio, threading
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Header, UploadFile, File, Form
from pydantic import BaseModel
from db import get_session, Seat, User, Reservation, Violation, ReleaseRecord, ReservationStatus
from .auth import verify_token


def _fire_broadcast(msg: dict):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(__import__("api.websocket", fromlist=["broadcast"]).broadcast(msg))
    except RuntimeError:
        threading.Thread(target=lambda: asyncio.run(
            __import__("api.websocket", fromlist=["broadcast"]).broadcast(msg)
        ), daemon=True).start()

router = APIRouter()
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

CHECKIN_WINDOW = 15
TEMP_LEAVE_MIN = 10
TEMP_LEAVE_INTERVAL_HOURS = 1
MAX_VIOLATIONS = 3


def get_current_user(authorization: str = Header("")) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return payload


def get_admin_user(payload: dict = Depends(get_current_user)) -> dict:
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return payload


def get_current_user_direct(authorization: str = Header("")) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return payload


def check_penalty(user: User):
    if user.is_admin:
        return
    if user.penalty_until and user.penalty_until > datetime.now():
        remaining = (user.penalty_until - datetime.now()).days + 1
        raise HTTPException(status_code=403, detail=f"账号处于违规暂停状态，剩余 {remaining} 天")


def count_violations_in_semester(session, user_id: int) -> int:
    semester_start = datetime(datetime.now().year, 2, 1) if datetime.now().month >= 2 else datetime(datetime.now().year - 1, 9, 1)
    if datetime.now().month >= 9:
        semester_start = datetime(datetime.now().year, 9, 1)
    return session.query(Violation).filter(
        Violation.user_id == user_id,
        Violation.created_at >= semester_start
    ).count()


def apply_penalty_if_needed(session, user_id: int):
    user = session.query(User).get(user_id)
    if user and user.is_admin:
        return
    count = count_violations_in_semester(session, user_id)
    if count >= MAX_VIOLATIONS and user:
        user.penalty_until = datetime.now() + timedelta(days=180)
        session.commit()


@router.get("/api/seats")
def list_seats(floor: int = None, payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        query = session.query(Seat).filter_by(is_active=True)
        if floor is not None:
            query = query.filter_by(floor=floor)
        seats = query.all()
        return [{
            "id": s.id, "floor": s.floor, "seat_number": s.seat_number,
            "category_letter": s.category_letter, "has_computer": s.has_computer,
        } for s in seats]
    finally:
        session.close()


@router.get("/api/seats/available")
def available_seats(floor: int = None, start_time: str = "", end_time: str = "",
                    payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        query = session.query(Seat).filter_by(is_active=True)
        if floor is not None:
            query = query.filter_by(floor=floor)
        seats = query.all()
        if start_time and end_time:
            try:
                st = datetime.fromisoformat(start_time)
                et = datetime.fromisoformat(end_time)
                occupied_ids = [
                    r.seat_id for r in session.query(Reservation).filter(
                        Reservation.status.in_([ReservationStatus.PENDING,
                                                ReservationStatus.CHECKED_IN,
                                                ReservationStatus.TEMP_LEAVE]),
                        Reservation.start_time < et,
                        Reservation.end_time > st,
                    ).all()
                ]
            except ValueError:
                occupied_ids = []
        else:
            occupied_ids = []
        return [{
            "id": s.id, "floor": s.floor, "seat_number": s.seat_number,
            "category_letter": s.category_letter, "has_computer": s.has_computer,
            "available": s.id not in occupied_ids,
        } for s in seats]
    finally:
        session.close()


@router.get("/api/seats/{seat_id}")
def get_seat(seat_id: int, payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        seat = session.query(Seat).get(seat_id)
        if not seat or not seat.is_active:
            raise HTTPException(status_code=404, detail="座位不存在")
        now = datetime.now()
        active_res = session.query(Reservation).filter(
            Reservation.seat_id == seat_id,
            Reservation.status.in_([ReservationStatus.PENDING,
                                    ReservationStatus.CHECKED_IN,
                                    ReservationStatus.TEMP_LEAVE]),
            Reservation.start_time <= now,
            Reservation.end_time >= now,
        ).first()
        return {
            "id": seat.id, "floor": seat.floor, "seat_number": seat.seat_number,
            "category_letter": seat.category_letter, "has_computer": seat.has_computer,
            "status": "空闲" if not active_res else active_res.status.value,
        }
    finally:
        session.close()


class ReserveRequest(BaseModel):
    seat_id: int
    start_time: datetime
    end_time: datetime


@router.post("/api/reservations")
def create_reservation(req: ReserveRequest, payload: dict = Depends(get_current_user)):
    user_id = payload["user_id"]
    session = get_session()
    try:
        user = session.query(User).get(user_id)
        check_penalty(user)
        seat = session.query(Seat).get(req.seat_id)
        if not seat or not seat.is_active:
            raise HTTPException(status_code=404, detail="座位不存在")
        active_count = session.query(Reservation).filter(
            Reservation.user_id == user_id,
            Reservation.status.in_([ReservationStatus.PENDING,
                                    ReservationStatus.CHECKED_IN,
                                    ReservationStatus.TEMP_LEAVE]),
        ).count()
        if active_count >= 1:
            raise HTTPException(status_code=400, detail="每人同时只能预约一个座位")
        conflict = session.query(Reservation).filter(
            Reservation.seat_id == req.seat_id,
            Reservation.status.in_([ReservationStatus.PENDING,
                                    ReservationStatus.CHECKED_IN,
                                    ReservationStatus.TEMP_LEAVE]),
            Reservation.start_time < req.end_time,
            Reservation.end_time > req.start_time,
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="该时段座位已被预约")
        res = Reservation(
            user_id=user_id, seat_id=req.seat_id,
            start_time=req.start_time, end_time=req.end_time,
        )
        session.add(res)
        session.commit()
        _fire_broadcast({"type": "seat_update", "seat_id": req.seat_id,
                         "status": "pending", "reservation_id": res.id})
        return {"message": "预约成功", "reservation_id": res.id}
    finally:
        session.close()


@router.get("/api/reservations/my")
def my_reservations(payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        res_list = session.query(Reservation).filter_by(
            user_id=payload["user_id"]
        ).order_by(Reservation.start_time.desc()).limit(20).all()
        return [{
            "id": r.id, "seat_id": r.seat_id,
            "seat_number": r.seat.seat_number,
            "floor": r.seat.floor,
            "start_time": r.start_time.isoformat(),
            "end_time": r.end_time.isoformat(),
            "status": r.status.value,
        } for r in res_list]
    finally:
        session.close()


@router.delete("/api/reservations/{res_id}")
def delete_reservation(res_id: int, payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        res = session.query(Reservation).get(res_id)
        if not res or res.user_id != payload["user_id"]:
            raise HTTPException(status_code=404, detail="预约不存在")
        if res.status in (ReservationStatus.PENDING, ReservationStatus.CHECKED_IN, ReservationStatus.TEMP_LEAVE):
            raise HTTPException(status_code=400, detail="进行中的预约无法删除，请先取消或签退")
        session.delete(res)
        session.commit()
        return {"message": "预约记录已删除"}
    finally:
        session.close()


@router.post("/api/reservations/{res_id}/cancel")
def cancel_reservation(res_id: int, payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        res = session.query(Reservation).get(res_id)
        if not res or res.user_id != payload["user_id"]:
            raise HTTPException(status_code=404, detail="预约不存在")
        if res.status != ReservationStatus.PENDING:
            raise HTTPException(status_code=400, detail=f"当前状态无法取消: {res.status.value}")
        if datetime.now() >= res.start_time:
            raise HTTPException(status_code=400, detail="预约已开始，无法取消")
        res.status = ReservationStatus.CANCELLED
        session.commit()
        _fire_broadcast({"type": "seat_update", "seat_id": res.seat_id,
                         "status": "free", "reservation_id": res.id})
        return {"message": "预约已取消"}
    finally:
        session.close()


@router.post("/api/reservations/{res_id}/checkin")
def checkin(res_id: int, payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        res = session.query(Reservation).get(res_id)
        if not res or res.user_id != payload["user_id"]:
            raise HTTPException(status_code=404, detail="预约不存在")
        if res.status not in (ReservationStatus.PENDING,):
            raise HTTPException(status_code=400, detail=f"当前状态无法签到: {res.status.value}")
        now = datetime.now()
        if now < res.start_time:
            raise HTTPException(status_code=400, detail="尚未到预约开始时间")
        if (now - res.start_time).total_seconds() > CHECKIN_WINDOW * 60:
            res.status = ReservationStatus.AUTO_RELEASED
            session.add(Violation(user_id=payload["user_id"],
                                  reservation_id=res_id,
                                  reason="超时未签到"))
            session.commit()
            apply_penalty_if_needed(session, payload["user_id"])
            raise HTTPException(status_code=400, detail="已超过签到时限，预约已自动取消")
        res.status = ReservationStatus.CHECKED_IN
        res.checkin_time = now
        session.commit()
        _fire_broadcast({"type": "seat_update", "seat_id": res.seat_id,
                         "status": "checked_in", "reservation_id": res.id})
        return {"message": "签到成功"}
    finally:
        session.close()


@router.post("/api/reservations/{res_id}/checkout")
def checkout(res_id: int, payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        res = session.query(Reservation).get(res_id)
        if not res or res.user_id != payload["user_id"]:
            raise HTTPException(status_code=404, detail="预约不存在")
        if res.status not in (ReservationStatus.CHECKED_IN, ReservationStatus.TEMP_LEAVE):
            raise HTTPException(status_code=400, detail=f"当前状态无法签退: {res.status.value}")
        res.status = ReservationStatus.COMPLETED
        res.temp_leave_start = None
        session.commit()
        _fire_broadcast({"type": "seat_update", "seat_id": res.seat_id,
                         "status": "free", "reservation_id": res.id})
        return {"message": "签退成功"}
    finally:
        session.close()


@router.post("/api/reservations/{res_id}/temp-leave")
def start_temp_leave(res_id: int, payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        res = session.query(Reservation).get(res_id)
        if not res or res.user_id != payload["user_id"]:
            raise HTTPException(status_code=404, detail="预约不存在")
        if res.status != ReservationStatus.CHECKED_IN:
            raise HTTPException(status_code=400, detail="当前状态无法暂离")
        elapsed_hours = (datetime.now() - res.start_time).total_seconds() / 3600
        max_allowed = int(elapsed_hours) + 1
        if res.temp_leave_count >= max_allowed:
            raise HTTPException(status_code=400,
                                detail=f"暂离次数已用完（每小时1次），已使用 {res.temp_leave_count} 次")
        now = datetime.now()
        if (now - res.start_time).total_seconds() > (res.end_time - res.start_time).total_seconds():
            raise HTTPException(status_code=400, detail="预约时间已结束")
        res.status = ReservationStatus.TEMP_LEAVE
        res.temp_leave_start = now
        res.temp_leave_count += 1
        session.commit()
        _fire_broadcast({"type": "seat_update", "seat_id": res.seat_id,
                         "status": "temp_leave", "reservation_id": res.id})
        return {"message": "暂离成功，请在10分钟内返回", "leave_count": res.temp_leave_count}
    finally:
        session.close()


@router.post("/api/reservations/{res_id}/temp-return")
def return_from_temp_leave(res_id: int, payload: dict = Depends(get_current_user)):
    session = get_session()
    try:
        res = session.query(Reservation).get(res_id)
        if not res or res.user_id != payload["user_id"]:
            raise HTTPException(status_code=404, detail="预约不存在")
        if res.status != ReservationStatus.TEMP_LEAVE:
            raise HTTPException(status_code=400, detail="当前状态无法返回")
        now = datetime.now()
        if res.temp_leave_start and (now - res.temp_leave_start).total_seconds() > TEMP_LEAVE_MIN * 60:
            res.status = ReservationStatus.AUTO_RELEASED
            session.add(Violation(user_id=payload["user_id"],
                                  reservation_id=res_id,
                                  reason="暂离超时未返回"))
            session.commit()
            apply_penalty_if_needed(session, payload["user_id"])
            raise HTTPException(status_code=400, detail="暂离超时，座位已自动释放")
        res.status = ReservationStatus.CHECKED_IN
        res.temp_leave_start = None
        session.commit()
        _fire_broadcast({"type": "seat_update", "seat_id": res.seat_id,
                         "status": "checked_in", "reservation_id": res.id})
        return {"message": "已返回座位"}
    finally:
        session.close()


@router.post("/api/admin/release-by-seat")
async def admin_release_by_seat(
    seat_number: str = Form(...),
    reason: str = Form(...),
    evidence: UploadFile = File(None),
    payload: dict = Depends(get_admin_user),
):
    session = get_session()
    try:
        seat = session.query(Seat).filter_by(seat_number=seat_number, is_active=True).first()
        if not seat:
            raise HTTPException(status_code=404, detail="座位不存在")
        now = datetime.now()
        res = session.query(Reservation).filter(
            Reservation.seat_id == seat.id,
            Reservation.status.in_([ReservationStatus.CHECKED_IN]),
        ).first()
        if not res:
            raise HTTPException(status_code=400, detail="该座位当前无已签到的有效预约")
        image_path = None
        if evidence:
            ext = os.path.splitext(evidence.filename)[1] if evidence.filename else ".jpg"
            filename = f"release_{res.id}_{uuid.uuid4().hex[:8]}{ext}"
            image_path = os.path.join(UPLOAD_DIR, filename)
            content = await evidence.read()
            with open(image_path, "wb") as f:
                f.write(content)
        record = ReleaseRecord(
            seat_id=res.seat_id, admin_id=payload["user_id"],
            reservation_id=res.id, reason=reason,
            evidence_image=image_path,
        )
        res.status = ReservationStatus.AUTO_RELEASED
        session.add(record)
        session.add(Violation(user_id=res.user_id, reservation_id=res.id,
                              reason=f"管理员释放: {reason}"))
        session.commit()
        apply_penalty_if_needed(session, res.user_id)
        _fire_broadcast({"type": "seat_update", "seat_id": res.seat_id,
                         "status": "free", "reservation_id": res.id})
        return {"message": "管理员已释放该座位", "evidence": image_path}
    finally:
        session.close()


@router.post("/api/admin/release/{res_id}")
async def admin_release(
    res_id: int,
    reason: str = Form(...),
    evidence: UploadFile = File(None),
    payload: dict = Depends(get_admin_user),
):
    session = get_session()
    try:
        res = session.query(Reservation).get(res_id)
        if not res:
            raise HTTPException(status_code=404, detail="预约不存在")
        if res.status in (ReservationStatus.COMPLETED, ReservationStatus.AUTO_RELEASED, ReservationStatus.CANCELLED):
            raise HTTPException(status_code=400, detail=f"预约已结束，无法释放")
        if res.status == ReservationStatus.TEMP_LEAVE:
            raise HTTPException(status_code=400, detail="暂离状态无法由管理员释放")
        image_path = None
        if evidence:
            ext = os.path.splitext(evidence.filename)[1] if evidence.filename else ".jpg"
            filename = f"release_{res_id}_{uuid.uuid4().hex[:8]}{ext}"
            image_path = os.path.join(UPLOAD_DIR, filename)
            content = await evidence.read()
            with open(image_path, "wb") as f:
                f.write(content)
        record = ReleaseRecord(
            seat_id=res.seat_id, admin_id=payload["user_id"],
            reservation_id=res_id, reason=reason,
            evidence_image=image_path,
        )
        res.status = ReservationStatus.AUTO_RELEASED
        session.add(record)
        session.add(Violation(user_id=res.user_id, reservation_id=res_id,
                              reason=f"管理员释放: {reason}"))
        session.commit()
        apply_penalty_if_needed(session, res.user_id)
        _fire_broadcast({"type": "seat_update", "seat_id": res.seat_id,
                         "status": "free", "reservation_id": res.id})
        return {"message": "管理员已释放该座位", "evidence": image_path}
    finally:
        session.close()


@router.get("/api/admin/release-records")
def get_release_records(payload: dict = Depends(get_admin_user)):
    session = get_session()
    try:
        records = session.query(ReleaseRecord).order_by(
            ReleaseRecord.created_at.desc()
        ).limit(50).all()
        return [{
            "id": r.id, "seat_id": r.seat_id, "admin_id": r.admin_id,
            "reason": r.reason, "evidence_image": r.evidence_image,
            "created_at": r.created_at.isoformat(),
            "seat_number": (session.query(Seat).get(r.seat_id).seat_number
                           if session.query(Seat).get(r.seat_id) else None),
        } for r in records]
    finally:
        session.close()


@router.get("/api/admin/users")
def admin_list_users(payload: dict = Depends(get_admin_user)):
    session = get_session()
    try:
        users = session.query(User).order_by(User.id).all()
        return [{
            "id": u.id, "student_id": u.student_id, "is_admin": u.is_admin,
            "penalty_until": u.penalty_until.isoformat() if u.penalty_until else None,
            "penalty_active": bool(u.penalty_until and u.penalty_until > datetime.now()),
        } for u in users]
    finally:
        session.close()


@router.post("/api/admin/users/{user_id}/toggle-penalty")
def admin_toggle_penalty(user_id: int, payload: dict = Depends(get_admin_user)):
    session = get_session()
    try:
        user = session.query(User).get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.is_admin:
            raise HTTPException(status_code=400, detail="不能暂停管理员账号")
        if user.penalty_until and user.penalty_until > datetime.now():
            user.penalty_until = None
            msg = "账号已解封"
        else:
            user.penalty_until = datetime.now() + timedelta(days=180)
            msg = "账号已暂停（180天）"
        session.commit()
        return {"message": msg, "penalty_until": user.penalty_until.isoformat() if user.penalty_until else None}
    finally:
        session.close()
