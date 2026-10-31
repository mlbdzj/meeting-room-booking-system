from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class MeetingRoom(Base):
    """会议室规格：属于某个空间，带时租价格、容纳人数和设备。"""

    __tablename__ = "meeting_room"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venue.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    layout: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    hourly_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    # 容纳人数（每间）
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # 同规格可用会议室数量
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    equipment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # open: 可预约，maintenance: 维护中，closed: 停用
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=func.now())

    venue = relationship("Venue", back_populates="meeting_rooms")
