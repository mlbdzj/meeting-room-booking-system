from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Reservation(Base):
    """会议室预约：在 [start_at, end_at) 区间占用若干间。"""

    __tablename__ = "reservation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venue.id"), nullable=False, index=True)
    meeting_room_id: Mapped[int] = mapped_column(ForeignKey("meeting_room.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), nullable=False, index=True)
    start_at: Mapped[object] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[object] = mapped_column(DateTime, nullable=False, index=True)
    hours: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1)
    rooms: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attendees: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    equipment_request: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # pending: 待确认，confirmed: 已确认，rejected: 已拒绝，canceled: 已取消，completed: 已完成
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    remark: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), nullable=True)
    reviewed_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=func.now())

    venue = relationship("Venue", back_populates="reservations")
    meeting_room = relationship("MeetingRoom")
    user = relationship("User", back_populates="reservations", foreign_keys=[user_id])
