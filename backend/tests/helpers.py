"""测试公共小工具：鉴权头、下单参数、造预约。"""

from datetime import date, timedelta

from app.core.security import create_access_token
from app.models import Reservation


def auth_headers(user) -> dict[str, str]:
    """按用户签发 Token，等价于前端登录后拿到的 Authorization 头。"""
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def reservation_payload(
    venue,
    meeting_room,
    *,
    days_from: int = 7,
    hours: int = 2,
    rooms: int = 1,
    attendees: int = 2,
    **extra,
) -> dict:
    check_in = date.today() + timedelta(days=days_from)
    payload = {
        "venue_id": venue.id,
        "meeting_room_id": meeting_room.id,
        "start_at": check_in.isoformat(),
        "end_at": (check_in + timedelta(days=hours)).isoformat(),
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
    hours: int = 2,
    rooms: int = 1,
    attendees: int = 2,
) -> Reservation:
    """直接落一条预约，用于构造库存占用场景。"""
    check_in = date.today() + timedelta(days=days_from)
    check_out = check_in + timedelta(days=hours)
    reservation = Reservation(
        venue_id=venue.id,
        meeting_room_id=meeting_room.id,
        user_id=user.id,
        start_at=check_in,
        end_at=check_out,
        hours=hours,
        rooms=rooms,
        attendees=attendees,
        contact_phone="13900000000",
        total_amount=float(meeting_room.price) * hours * rooms,
        equipment_request="",
        status=status,
        remark="",
    )
    db.add(reservation)
    db.flush()
    return reservation
