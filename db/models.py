# db/models.py - SQLAlchemy ORM 模型定义（User/Seat/Reservation/Violation/ReleaseRecord）

import enum
from datetime import datetime
from sqlalchemy import (Column, Integer, String, Boolean, DateTime, Enum,
                        ForeignKey, Text, create_engine)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CHECKED_IN = "checked_in"
    TEMP_LEAVE = "temp_leave"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    AUTO_RELEASED = "auto_released"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    name = Column(String(50), nullable=False)
    penalty_until = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)

    reservations = relationship("Reservation", back_populates="user")
    violations = relationship("Violation", back_populates="user")
    release_records = relationship("ReleaseRecord", back_populates="admin",
                                   foreign_keys="ReleaseRecord.admin_id")


class Seat(Base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor = Column(Integer, nullable=False)
    seat_number = Column(String(10), nullable=False)
    category_letter = Column(String(5), nullable=True)
    has_computer = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    reservations = relationship("Reservation", back_populates="seat")
    release_records = relationship("ReleaseRecord", back_populates="seat")


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seat_id = Column(Integer, ForeignKey("seats.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.PENDING)
    checkin_time = Column(DateTime, nullable=True)
    temp_leave_start = Column(DateTime, nullable=True)
    temp_leave_count = Column(Integer, default=0)

    user = relationship("User", back_populates="reservations")
    seat = relationship("Seat", back_populates="reservations")
    violations = relationship("Violation", back_populates="reservation")


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="violations")
    reservation = relationship("Reservation", back_populates="violations")


class ReleaseRecord(Base):
    __tablename__ = "release_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seat_id = Column(Integer, ForeignKey("seats.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    reason = Column(Text, nullable=False)
    evidence_image = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    seat = relationship("Seat", back_populates="release_records")
    admin = relationship("User", back_populates="release_records",
                         foreign_keys=[admin_id])
