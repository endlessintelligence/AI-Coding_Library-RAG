# db/operations.py - 数据库初始化和 CRUD 操作

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from .models import Base, User, Seat, Reservation, Violation, ReleaseRecord, ReservationStatus


DATABASE_URL = "sqlite:///./library.db"
engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)


def seed_initial_data():
    session = get_session()
    try:
        if session.query(Seat).count() > 0:
            return
        for floor in [-1, 2, 3, 4, 5]:
            category = {2: "A-F", 3: "G-L", 4: "M-R", 5: "S-Z"}.get(floor, "")
            has_pc = floor == -1
            seat_count = 20 if floor == -1 else 30
            for i in range(1, seat_count + 1):
                session.add(Seat(
                    floor=floor,
                    seat_number=f"{floor}F-{i:03d}",
                    category_letter=category,
                    has_computer=has_pc,
                ))
        admin = User(
            student_id="admin",
            password_hash="",
            name="管理员",
            is_admin=True,
        )
        session.add(admin)
        session.commit()
    finally:
        session.close()
