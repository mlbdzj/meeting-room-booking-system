"""测试公共工具：鉴权头、时间段参数与预约造数。"""

from datetime import date, datetime, time, timedelta

from app.core.security import create_access_token
from app.models import Reservation


def auth_headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def slot(
    *,
    days_from: int = 7,
    hour: int = 10,
    hours: float = 2,
) -> tuple[datetime, datetime]:
    start_at = datetime.combine(
        date.today() + timedelta(days=days_from),
        time(hour, 0),
    )
    return start_at, start_at + timedelta(hours=hours)


def reservation_payload(
    venue,
    meeting_room,
    *,
    days_from: int = 7,
    hour: int = 10,
    hours: float = 2,
    rooms: int = 1,
    attendees: int = 2,
    **extra,
) -> dict:
    start_at, end_at = slot(days_from=days_from, hour=hour, hours=hours)
    payload = {
        "venue_id": venue.id,
        "meeting_room_id": meeting_room.id,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "rooms": rooms,
        "attendees": attendees,
    }
    payload.update(extra)
    return payload


def seed_reservation(
    db,
    *,
    user,
    venue,
    meeting_room,
    status: str = "pending",
    days_from: int = 7,
    hour: int = 10,
    hours: float = 2,
    rooms: int = 1,
    attendees: int = 2,
) -> Reservation:
    start_at, end_at = slot(
        days_from=days_from,
        hour=hour,
        hours=hours,
    )
    reservation = Reservation(
        venue_id=venue.id,
        meeting_room_id=meeting_room.id,
        user_id=user.id,
        start_at=start_at,
        end_at=end_at,
        hours=hours,
        rooms=rooms,
        attendees=attendees,
        contact_phone="13900000000",
        total_amount=float(meeting_room.hourly_price) * hours * rooms,
        equipment_request="",
        status=status,
        remark="",
    )
    db.add(reservation)
    db.flush()
    return reservation
