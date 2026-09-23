from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    # admin: 管理员，user: 普通用户
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    # 1: 正常，0: 禁用
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=func.now())

    reservations = relationship(
        "Reservation", back_populates="user", foreign_keys="Reservation.user_id"
    )
