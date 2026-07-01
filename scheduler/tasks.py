# scheduler/tasks.py - 定时任务（超时未签到释放 + 暂离超时释放 + 违规记录）

from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from db import get_session, Reservation, Violation, User, ReservationStatus


CHECKIN_WINDOW_MINUTES = 15
TEMP_LEAVE_MINUTES = 10
MAX_VIOLATIONS = 3
SCAN_INTERVAL_SECONDS = 30


def release_expired_pending():
    session = get_session()
    try:
        deadline = datetime.now() - timedelta(minutes=CHECKIN_WINDOW_MINUTES)
        expired = session.query(Reservation).filter(
            Reservation.status == ReservationStatus.PENDING,
            Reservation.start_time < deadline,
        ).all()
        for res in expired:
            res.status = ReservationStatus.AUTO_RELEASED
            session.add(Violation(
                user_id=res.user_id,
                reservation_id=res.id,
                reason="超时未签到",
            ))
        if expired:
            session.commit()
            for res in expired:
                _apply_penalty_if_needed(session, res.user_id)
            session.commit()
            print(f"[Scheduler] 自动释放 {len(expired)} 条超时未签到预约")
    except Exception as e:
        print(f"[Scheduler] 释放超时预约异常: {e}")
    finally:
        session.close()


def release_expired_temp_leave():
    session = get_session()
    try:
        deadline = datetime.now() - timedelta(minutes=TEMP_LEAVE_MINUTES)
        expired = session.query(Reservation).filter(
            Reservation.status == ReservationStatus.TEMP_LEAVE,
            Reservation.temp_leave_start < deadline,
        ).all()
        for res in expired:
            res.status = ReservationStatus.AUTO_RELEASED
            res.temp_leave_start = None
            session.add(Violation(
                user_id=res.user_id,
                reservation_id=res.id,
                reason="暂离超时未返回",
            ))
        if expired:
            session.commit()
            for res in expired:
                _apply_penalty_if_needed(session, res.user_id)
            session.commit()
            print(f"[Scheduler] 自动释放 {len(expired)} 条暂离超时预约")
    except Exception as e:
        print(f"[Scheduler] 释放暂离超时异常: {e}")
    finally:
        session.close()


def _apply_penalty_if_needed(session, user_id: int):
    semester_start = _get_semester_start()
    count = session.query(Violation).filter(
        Violation.user_id == user_id,
        Violation.created_at >= semester_start,
    ).count()
    if count >= MAX_VIOLATIONS:
        user = session.query(User).get(user_id)
        if user and user.is_admin:
            return
        if user and (not user.penalty_until or user.penalty_until < datetime.now()):
            user.penalty_until = datetime.now() + timedelta(days=180)
            print(f"[Scheduler] 用户 {user_id} 违规达 {count} 次，暂停预约资格至 {user.penalty_until}")


def _get_semester_start() -> datetime:
    now = datetime.now()
    year = now.year
    if now.month >= 9:
        return datetime(year, 9, 1)
    elif now.month >= 2:
        return datetime(year, 2, 1)
    else:
        return datetime(year - 1, 9, 1)


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(release_expired_pending, "interval",
                      seconds=SCAN_INTERVAL_SECONDS,
                      id="release_pending", name="释放超时未签到")
    scheduler.add_job(release_expired_temp_leave, "interval",
                      seconds=SCAN_INTERVAL_SECONDS,
                      id="release_temp_leave", name="释放暂离超时")
    scheduler.start()
    print("[Scheduler] 定时任务已启动（每30秒扫描）")
    return scheduler
