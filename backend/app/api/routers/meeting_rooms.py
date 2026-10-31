from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.serializers import meeting_room_to_dict
from app.db.session import get_db
from app.models import MeetingRoom, Reservation, User, Venue
from app.schemas.common import Message, Page
from app.schemas.meeting_room import MeetingRoomIn, MeetingRoomOut

router = APIRouter(prefix="/api/meeting-rooms", tags=["会议室管理"])


def _venue_name_map(db: Session, venue_ids: list[int]) -> dict[int, str]:
    if not venue_ids:
        return {}
    rows = db.execute(
        select(Venue.id, Venue.name).where(Venue.id.in_(venue_ids))
    ).all()
    return {row[0]: row[1] for row in rows}


@router.get("", response_model=Page[MeetingRoomOut])
def list_meeting_rooms(
    keyword: str = Query(default=""),
    venue_id: int | None = Query(default=None),
    status_filter: str = Query(default="", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = []
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(
            MeetingRoom.name.like(like)
            | MeetingRoom.code.like(like)
            | MeetingRoom.layout.like(like)
            | MeetingRoom.equipment.like(like)
        )
    if venue_id:
        conditions.append(MeetingRoom.venue_id == venue_id)
    if status_filter:
        conditions.append(MeetingRoom.status == status_filter)

    total = db.scalar(select(func.count(MeetingRoom.id)).where(*conditions)) or 0
    meeting_rooms = db.scalars(
        select(MeetingRoom)
        .where(*conditions)
        .order_by(MeetingRoom.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    names = _venue_name_map(db, [item.venue_id for item in meeting_rooms])
    return {
        "total": total,
        "items": [
            meeting_room_to_dict(item, names.get(item.venue_id, ""))
            for item in meeting_rooms
        ],
    }


@router.get("/all", response_model=list[MeetingRoomOut])
def list_all_meeting_rooms(
    venue_id: int | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = []
    if venue_id:
        conditions.append(MeetingRoom.venue_id == venue_id)
    meeting_rooms = db.scalars(
        select(MeetingRoom)
        .where(*conditions)
        .order_by(MeetingRoom.hourly_price.asc())
    ).all()
    names = _venue_name_map(db, [item.venue_id for item in meeting_rooms])
    return [
        meeting_room_to_dict(item, names.get(item.venue_id, ""))
        for item in meeting_rooms
    ]


@router.post("", response_model=MeetingRoomOut, status_code=status.HTTP_201_CREATED)
def create_meeting_room(
    payload: MeetingRoomIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    venue = db.get(Venue, payload.venue_id)
    if venue is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所属空间不存在")
    if payload.code and db.scalar(
        select(MeetingRoom).where(MeetingRoom.code == payload.code)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会议室编号已存在")
    meeting_room = MeetingRoom(**payload.model_dump())
    db.add(meeting_room)
    db.commit()
    db.refresh(meeting_room)
    return meeting_room_to_dict(meeting_room, venue.name)


@router.put("/{meeting_room_id}", response_model=MeetingRoomOut)
def update_meeting_room(
    meeting_room_id: int,
    payload: MeetingRoomIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    meeting_room = db.get(MeetingRoom, meeting_room_id)
    if meeting_room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议室不存在")
    venue = db.get(Venue, payload.venue_id)
    if venue is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所属空间不存在")
    if payload.code and db.scalar(
        select(MeetingRoom).where(
            MeetingRoom.code == payload.code,
            MeetingRoom.id != meeting_room_id,
        )
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会议室编号已存在")
    for field, value in payload.model_dump().items():
        setattr(meeting_room, field, value)
    db.commit()
    db.refresh(meeting_room)
    return meeting_room_to_dict(meeting_room, venue.name)


@router.delete("/{meeting_room_id}", response_model=Message)
def delete_meeting_room(
    meeting_room_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    meeting_room = db.get(MeetingRoom, meeting_room_id)
    if meeting_room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议室不存在")
    if db.scalar(
        select(func.count(Reservation.id)).where(
            Reservation.meeting_room_id == meeting_room_id
        )
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该会议室已有预约记录，无法删除")
    db.delete(meeting_room)
    db.commit()
    return Message(message="删除成功")
