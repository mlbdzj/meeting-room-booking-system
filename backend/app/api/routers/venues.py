from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.serializers import MEETING_ROOM_STATUS_TEXT, venue_to_dict
from app.db.session import get_db
from app.models import MeetingRoom, Reservation, User, Venue
from app.schemas.common import Message, Page
from app.schemas.venue import VenueIn, VenueOut
from app.services.reservation_service import duration_hours, remaining_rooms

router = APIRouter(prefix="/api/venues", tags=["空间管理"])


def _counts(db: Session, venue_ids: list[int]) -> dict[int, dict[str, int]]:
    result = {
        venue_id: {"meeting_room_count": 0, "reservation_count": 0}
        for venue_id in venue_ids
    }
    if not venue_ids:
        return result
    for venue_id, count in db.execute(
        select(MeetingRoom.venue_id, func.count(MeetingRoom.id))
        .where(MeetingRoom.venue_id.in_(venue_ids))
        .group_by(MeetingRoom.venue_id)
    ).all():
        result[venue_id]["meeting_room_count"] = count
    for venue_id, count in db.execute(
        select(Reservation.venue_id, func.count(Reservation.id))
        .where(Reservation.venue_id.in_(venue_ids))
        .group_by(Reservation.venue_id)
    ).all():
        result[venue_id]["reservation_count"] = count
    return result


@router.get("", response_model=Page[VenueOut])
def list_venues(
    keyword: str = Query(default=""),
    city: str = Query(default=""),
    status_filter: int | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = []
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(Venue.name.like(like) | Venue.address.like(like))
    if city:
        conditions.append(Venue.city == city)
    if status_filter is not None:
        conditions.append(Venue.status == status_filter)

    total = db.scalar(select(func.count(Venue.id)).where(*conditions)) or 0
    venues = db.scalars(
        select(Venue)
        .where(*conditions)
        .order_by(Venue.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    counts = _counts(db, [venue.id for venue in venues])
    return {
        "total": total,
        "items": [
            venue_to_dict(
                venue,
                counts[venue.id]["meeting_room_count"],
                counts[venue.id]["reservation_count"],
            )
            for venue in venues
        ],
    }


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(
    venue_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空间不存在")
    counts = _counts(db, [venue.id])
    return venue_to_dict(
        venue,
        counts[venue.id]["meeting_room_count"],
        counts[venue.id]["reservation_count"],
    )


@router.get("/{venue_id}/availability")
def venue_availability(
    venue_id: int,
    start_at: datetime = Query(description="开始时间，ISO 8601"),
    end_at: datetime = Query(description="结束时间，ISO 8601"),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空间不存在")
    if end_at <= start_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="结束时间必须晚于开始时间")

    meeting_rooms = db.scalars(
        select(MeetingRoom)
        .where(MeetingRoom.venue_id == venue_id)
        .order_by(MeetingRoom.hourly_price.asc())
    ).all()
    items = []
    for meeting_room in meeting_rooms:
        remaining = remaining_rooms(db, meeting_room, start_at, end_at)
        items.append(
            {
                "id": meeting_room.id,
                "name": meeting_room.name,
                "layout": meeting_room.layout,
                "hourly_price": float(meeting_room.hourly_price or 0),
                "capacity": meeting_room.capacity,
                "quantity": meeting_room.quantity,
                "equipment": meeting_room.equipment,
                "remaining": remaining,
                "status": meeting_room.status,
                "status_text": MEETING_ROOM_STATUS_TEXT.get(
                    meeting_room.status, meeting_room.status
                ),
                "available": meeting_room.status == "open" and remaining > 0,
            }
        )

    return {
        "venue_id": venue_id,
        "venue_name": venue.name,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "hours": duration_hours(start_at, end_at),
        "open_time": venue.open_time,
        "close_time": venue.close_time,
        "meeting_rooms": items,
    }


@router.post("", response_model=VenueOut, status_code=status.HTTP_201_CREATED)
def create_venue(
    payload: VenueIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(Venue).where(Venue.name == payload.name)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空间名称已存在")
    venue = Venue(**payload.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue_to_dict(venue)


@router.put("/{venue_id}", response_model=VenueOut)
def update_venue(
    venue_id: int,
    payload: VenueIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空间不存在")
    duplicated = db.scalar(
        select(Venue).where(Venue.name == payload.name, Venue.id != venue_id)
    )
    if duplicated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="空间名称已存在")
    for field, value in payload.model_dump().items():
        setattr(venue, field, value)
    db.commit()
    db.refresh(venue)
    counts = _counts(db, [venue.id])
    return venue_to_dict(
        venue,
        counts[venue.id]["meeting_room_count"],
        counts[venue.id]["reservation_count"],
    )


@router.delete("/{venue_id}", response_model=Message)
def delete_venue(
    venue_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="空间不存在")
    if db.scalar(select(func.count(Reservation.id)).where(Reservation.venue_id == venue_id)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该空间已有预约记录，无法删除")
    if db.scalar(select(func.count(MeetingRoom.id)).where(MeetingRoom.venue_id == venue_id)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先删除该空间下的会议室")
    db.delete(venue)
    db.commit()
    return Message(message="删除成功")
