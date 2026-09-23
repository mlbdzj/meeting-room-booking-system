from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class MeetingRoom(Base):
    """会议室类型：属于某家会议空间，带价格、可住人数与会议室余量（库存）。"""

    __tablename__ = "meeting_room"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venue.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    layout: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    # 可住人数（每间）
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # 会议室余量，也就是该会议室类型的库存间数
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # open: 可预约，maintenance: 维护中，closed: 停售
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=func.now())

    venue = relationship("Venue", back_populates="meeting_rooms")
