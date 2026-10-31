"""会议室预约规则：页面与 Agent 共用同一套时间、容量和库存校验。"""

from datetime import datetime, time
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MeetingRoom, Reservation, User, Venue
from app.schemas.reservation import ReservationIn

# 待确认与已确认的预约都会占用会议室库存
ACTIVE_STATUS = ("pending", "confirmed")


def duration_hours(start_at: datetime, end_at: datetime) -> float:
    return round((end_at - start_at).total_seconds() / 3600, 2)


def occupied_rooms(
    db: Session,
    meeting_room_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_id: int | None = None,
) -> int:
    """统计与 [start_at, end_at) 重叠的有效预约占用的会议室数量。"""
    conditions = [
        Reservation.meeting_room_id == meeting_room_id,
        Reservation.status.in_(ACTIVE_STATUS),
        Reservation.start_at < end_at,
        Reservation.end_at > start_at,
    ]
    if exclude_id:
        conditions.append(Reservation.id != exclude_id)
    return db.scalar(select(func.coalesce(func.sum(Reservation.rooms), 0)).where(*conditions)) or 0


def remaining_rooms(
    db: Session,
    meeting_room: MeetingRoom,
    start_at: datetime,
    end_at: datetime,
    exclude_id: int | None = None,
) -> int:
    return max(
        0,
        meeting_room.quantity
        - occupied_rooms(db, meeting_room.id, start_at, end_at, exclude_id),
    )


def validate_reservation(
    db: Session, user: User, payload: ReservationIn
) -> tuple[Venue, MeetingRoom]:
    """校验预约是否可提交，返回 (空间, 会议室规格)。"""
    venue = db.get(Venue, payload.venue_id)
    if venue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空间不存在")
    if venue.status != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该空间暂未开放预约")

    meeting_room = db.get(MeetingRoom, payload.meeting_room_id)
    if meeting_room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议室不存在")
    if meeting_room.venue_id != venue.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该会议室不属于所选空间")
    if meeting_room.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该会议室暂不可预约")

    if payload.start_at < datetime.now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="开始时间不能早于当前时间")
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="结束时间必须晚于开始时间")

    open_time = time.fromisoformat(venue.open_time)
    close_time = time.fromisoformat(venue.close_time)
    if payload.start_at.time() < open_time or payload.end_at.time() > close_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"预约时间需在该空间开放时段 {venue.open_time}-{venue.close_time} 内",
        )

    if payload.rooms > meeting_room.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"该会议室仅有 {meeting_room.quantity} 间",
        )
    if payload.attendees > meeting_room.capacity * payload.rooms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"参会人数超过上限（每间可容纳 {meeting_room.capacity} 人，"
                f"共 {payload.rooms} 间）"
            ),
        )

    remaining = remaining_rooms(db, meeting_room, payload.start_at, payload.end_at)
    if payload.rooms > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{payload.start_at:%Y-%m-%d %H:%M} 至 {payload.end_at:%Y-%m-%d %H:%M} "
                f"期间该会议室仅剩 {remaining} 间可预约"
            ),
        )
    return venue, meeting_room


def build_reservation(db: Session, user: User, payload: ReservationIn) -> Reservation:
    """校验并构造尚未落库的预约对象，包含时长与总价。"""
    venue, meeting_room = validate_reservation(db, user, payload)
    hours = Decimal(str(duration_hours(payload.start_at, payload.end_at)))
    total_amount = Decimal(str(meeting_room.hourly_price)) * hours * payload.rooms

    return Reservation(
        venue_id=venue.id,
        meeting_room_id=meeting_room.id,
        user_id=user.id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        hours=hours,
        rooms=payload.rooms,
        attendees=payload.attendees,
        contact_phone=payload.contact_phone or user.phone or "",
        total_amount=total_amount,
        equipment_request=payload.equipment_request,
        status="pending",
        remark="",
    )


def create_reservation(db: Session, user: User, payload: ReservationIn) -> Reservation:
    reservation = build_reservation(db, user, payload)
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation
