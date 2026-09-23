from datetime import date, datetime

from app.models import Reservation, Venue, MeetingRoom, User

RESERVATION_STATUS_TEXT = {
    "pending": "待确认",
    "confirmed": "已确认",
    "rejected": "已拒绝",
    "canceled": "已取消",
    "completed": "已完成",
}

MEETING_ROOM_STATUS_TEXT = {
    "open": "可预约",
    "maintenance": "维护中",
    "closed": "停售",
}


def venue_to_dict(venue: Venue, meeting_room_count: int = 0, reservation_count: int = 0) -> dict:
    return {
        "id": venue.id,
        "name": venue.name,
        "city": venue.city,
        "address": venue.address,
        "star": venue.star,
        "room_count": venue.room_count,
        "open_time": venue.open_time,
        "close_time": venue.close_time,
        "status": venue.status,
        "description": venue.description,
        "created_at": venue.created_at,
        "meeting_room_count": meeting_room_count,
        "reservation_count": reservation_count,
    }


def meeting_room_to_dict(meeting_room: MeetingRoom, venue_name: str = "") -> dict:
    return {
        "id": meeting_room.id,
        "name": meeting_room.name,
        "code": meeting_room.code,
        "layout": meeting_room.layout,
        "venue_id": meeting_room.venue_id,
        "venue_name": venue_name,
        "price": float(meeting_room.price or 0),
        "capacity": meeting_room.capacity,
        "quantity": meeting_room.quantity,
        "status": meeting_room.status,
        "description": meeting_room.description,
        "created_at": meeting_room.created_at,
    }


def reservation_to_dict(
    reservation: Reservation,
    venue_name: str = "",
    meeting_room_name: str = "",
    user: User | None = None,
    reviewer: User | None = None,
) -> dict:
    return {
        "id": reservation.id,
        "venue_id": reservation.venue_id,
        "venue_name": venue_name,
        "meeting_room_id": reservation.meeting_room_id,
        "meeting_room_name": meeting_room_name,
        "user_id": reservation.user_id,
        "username": user.username if user else "",
        "user_name": (user.name or user.username) if user else "",
        "start_at": reservation.start_at,
        "end_at": reservation.end_at,
        "hours": reservation.hours,
        "rooms": reservation.rooms,
        "attendees": reservation.attendees,
        "contact_phone": reservation.contact_phone,
        "total_amount": float(reservation.total_amount or 0),
        "equipment_request": reservation.equipment_request,
        "status": reservation.status,
        "status_text": RESERVATION_STATUS_TEXT.get(reservation.status, reservation.status),
        "remark": reservation.remark,
        "reviewer_name": (reviewer.name or reviewer.username) if reviewer else "",
        "reviewed_at": reservation.reviewed_at,
        "created_at": reservation.created_at,
    }


def refresh_completed_status(db, reservations: list[Reservation]) -> None:
    """使用结束日期已过的已确认预约，自动标记为已完成。"""
    today = date.today()
    changed = False
    for reservation in reservations:
        if reservation.status == "confirmed" and reservation.end_at < today:
            reservation.status = "completed"
            changed = True
    if changed:
        db.commit()
