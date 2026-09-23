"""预约业务规则：页面下单与助手下单共用同一套校验（含会议室余量库存与防超卖）。"""

from datetime import date as date_type
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Reservation, Venue, MeetingRoom, User
from app.schemas.reservation import ReservationIn

# 占用会议室余量的预约状态：待确认与已确认都会占住库存
ACTIVE_STATUS = ("pending", "confirmed")


def hours_between(check_in: date_type, check_out: date_type) -> int:
    return (check_out - check_in).days


def occupied_rooms(
    db: Session,
    meeting_room_id: int,
    check_in: date_type,
    check_out: date_type,
    exclude_id: int | None = None,
) -> int:
    """统计与 [check_in, check_out) 有重叠的有效预约已占用的间数。"""
    conditions = [
        Reservation.meeting_room_id == meeting_room_id,
        Reservation.status.in_(ACTIVE_STATUS),
        Reservation.start_at < check_out,
        Reservation.end_at > check_in,
    ]
    if exclude_id:
        conditions.append(Reservation.id != exclude_id)
    return db.scalar(select(func.coalesce(func.sum(Reservation.rooms), 0)).where(*conditions)) or 0


def remaining_rooms(
    db: Session,
    meeting_room: MeetingRoom,
    check_in: date_type,
    check_out: date_type,
    exclude_id: int | None = None,
) -> int:
    return max(0, meeting_room.quantity - occupied_rooms(db, meeting_room.id, check_in, check_out, exclude_id))


def validate_reservation(db: Session, user: User, payload: ReservationIn) -> tuple[Venue, MeetingRoom]:
    """校验预约是否可下单，返回 (会议空间, 会议室类型)；不合法时抛 HTTPException。"""
    venue = db.get(Venue, payload.venue_id)
    if venue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议空间不存在")
    if venue.status != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该会议空间暂停营业")

    meeting_room = db.get(MeetingRoom, payload.meeting_room_id)
    if meeting_room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议室类型不存在")
    if meeting_room.venue_id != venue.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该会议室类型不属于所选会议空间")
    if meeting_room.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该会议室类型暂不可预约")

    if payload.start_at < date_type.today():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="使用开始日期不能早于今天")
    if payload.rooms > meeting_room.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"该会议室类型会议室余量只有 {meeting_room.quantity} 间"
        )
    if payload.attendees > meeting_room.capacity * payload.rooms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"使用开始人数超过上限（每间可住 {meeting_room.capacity} 人，共 {payload.rooms} 间）",
        )

    remaining = remaining_rooms(db, meeting_room, payload.start_at, payload.end_at)
    if payload.rooms > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{payload.start_at} 至 {payload.end_at} 期间该会议室类型仅剩 {remaining} 间可订"
            ),
        )
    return venue, meeting_room


def build_reservation(db: Session, user: User, payload: ReservationIn) -> Reservation:
    """校验并构造（未落库）的预约对象，含晚数与总价计算。"""
    venue, meeting_room = validate_reservation(db, user, payload)
    hours = hours_between(payload.start_at, payload.end_at)
    total_amount = Decimal(str(meeting_room.price)) * hours * payload.rooms

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
