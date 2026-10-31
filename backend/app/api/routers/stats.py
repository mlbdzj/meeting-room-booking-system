from datetime import date as date_type
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.serializers import refresh_completed_status, reservation_to_dict
from app.db.session import get_db
from app.models import MeetingRoom, Reservation, User, Venue
from app.services.reservation_service import ACTIVE_STATUS

router = APIRouter(prefix="/api/stats", tags=["统计"])

COUNTED_STATUS = ("pending", "confirmed", "completed")


@router.get("/overview")
def overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date_type.today()
    day_start = datetime.combine(today, time.min)
    day_end = day_start + timedelta(days=1)
    is_admin = current_user.role == "admin"
    scope = [] if is_admin else [Reservation.user_id == current_user.id]

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_start_at = datetime.combine(week_start, time.min)
    week_end_at = datetime.combine(week_end + timedelta(days=1), time.min)

    venue_total = db.scalar(select(func.count(Venue.id))) or 0
    meeting_room_total = db.scalar(select(func.count(MeetingRoom.id))) or 0
    user_total = db.scalar(select(func.count(User.id))) or 0
    reservation_total = (
        db.scalar(select(func.count(Reservation.id)).where(*scope)) or 0
    )
    pending_total = (
        db.scalar(
            select(func.count(Reservation.id)).where(
                *scope, Reservation.status == "pending"
            )
        )
        or 0
    )
    today_reservation_total = (
        db.scalar(
            select(func.count(Reservation.id)).where(
                *scope,
                Reservation.start_at < day_end,
                Reservation.end_at > day_start,
                Reservation.status.in_(ACTIVE_STATUS),
            )
        )
        or 0
    )
    week_total = (
        db.scalar(
            select(func.count(Reservation.id)).where(
                *scope,
                Reservation.start_at >= week_start_at,
                Reservation.start_at < week_end_at,
                Reservation.status.in_(COUNTED_STATUS),
            )
        )
        or 0
    )

    # 会议空间使用率的简化口径：今日被有效预约占用的会议室数量 / 全部会议室数量。
    total_rooms = (
        db.scalar(select(func.coalesce(func.sum(MeetingRoom.quantity), 0))) or 0
    )
    occupied_today = (
        db.scalar(
            select(func.coalesce(func.sum(Reservation.rooms), 0)).where(
                Reservation.status.in_(ACTIVE_STATUS),
                Reservation.start_at < day_end,
                Reservation.end_at > day_start,
            )
        )
        or 0
    )
    utilization_rate = (
        round(occupied_today * 100 / total_rooms) if total_rooms else 0
    )

    ranking_rows = db.execute(
        select(Venue.id, Venue.name, func.count(Reservation.id))
        .join(
            Reservation,
            (Reservation.venue_id == Venue.id)
            & (Reservation.start_at >= week_start_at)
            & (Reservation.start_at < week_end_at)
            & (Reservation.status.in_(COUNTED_STATUS)),
            isouter=True,
        )
        .group_by(Venue.id, Venue.name)
        .order_by(func.count(Reservation.id).desc(), Venue.id.asc())
    ).all()
    venue_ranking = [
        {
            "venue_id": row[0],
            "venue_name": row[1],
            "reservation_count": row[2],
        }
        for row in ranking_rows
    ]

    recent = db.scalars(
        select(Reservation)
        .where(*scope)
        .order_by(Reservation.created_at.desc(), Reservation.id.desc())
        .limit(6)
    ).all()
    refresh_completed_status(db, list(recent))

    venue_names = dict(db.execute(select(Venue.id, Venue.name)).all())
    meeting_room_names = dict(
        db.execute(select(MeetingRoom.id, MeetingRoom.name)).all()
    )
    user_ids = {item.user_id for item in recent}
    users = {
        user.id: user
        for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    }

    return {
        "venue_total": venue_total,
        "meeting_room_total": meeting_room_total,
        "user_total": user_total,
        "reservation_total": reservation_total,
        "pending_total": pending_total,
        "today_reservation_total": today_reservation_total,
        "utilization_rate": utilization_rate,
        "week_total": week_total,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "venue_ranking": venue_ranking,
        "recent_reservations": [
            reservation_to_dict(
                item,
                venue_names.get(item.venue_id, ""),
                meeting_room_names.get(item.meeting_room_id, ""),
                users.get(item.user_id),
            )
            for item in recent
        ],
    }
