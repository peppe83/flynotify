"""Modelli ORM. Tipi volutamente generici per girare su MySQL e SQLite."""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")          # user|admin|superadmin
    status: Mapped[str] = mapped_column(String(20), default="active")       # active|suspended
    poll_interval_hours: Mapped[int] = mapped_column(Integer, default=6)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timezone: Mapped[str] = mapped_column(String(40), default="Europe/Rome")
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    verified: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    alerts: Mapped[list["Alert"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))          # IATA oppure 'ANY'
    depart_from: Mapped[date] = mapped_column(Date)
    depart_to: Mapped[date] = mapped_column(Date)
    return_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    return_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    adults: Mapped[int] = mapped_column(Integer, default=1)
    cabin: Mapped[str] = mapped_column(String(20), default="ECONOMY")
    max_stops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depart_dow: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 1=Lun..7=Dom
    return_dow: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depart_time_from: Mapped[str | None] = mapped_column(String(5), nullable=True)  # 'HH:MM'
    depart_time_to: Mapped[str | None] = mapped_column(String(5), nullable=True)
    target_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    strategy: Mapped[str] = mapped_column(String(20), default="threshold")   # threshold|drop|deal
    status: Mapped[str] = mapped_column(String(20), default="active")        # active|paused
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped["User"] = relationship(back_populates="alerts")
    history: Mapped[list["PriceHistory"]] = relationship(back_populates="alert", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(36), ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    offer_json: Mapped[dict] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    alert: Mapped["Alert"] = relationship(back_populates="history")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    alert_id: Mapped[str] = mapped_column(String(36), ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    reason: Mapped[str] = mapped_column(String(20))
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AppSetting(Base):
    __tablename__ = "app_settings"

    setting_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    setting_value: Mapped[str] = mapped_column(String(255))


class RunLog(Base):
    __tablename__ = "run_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    users_checked: Mapped[int] = mapped_column(Integer, default=0)
    alerts_checked: Mapped[int] = mapped_column(Integer, default=0)
    emails_sent: Mapped[int] = mapped_column(Integer, default=0)
    api_calls: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmailLog(Base):
    __tablename__ = "email_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    to_email: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
