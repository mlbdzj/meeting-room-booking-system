from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.serializers import refresh_completed_status, reservation_to_dict
from app.db.session import get_db
from app.models import MeetingRoom, Reservation, User, Venue
from app.schemas.common import Message, Page
from app.schemas.reservation import ReservationIn, ReservationOut, ReservationReview
from app.services.reservation_service import ACTIVE_STATUS, create_reservation, remaining_rooms

router = APIRouter(prefix="/api/reservations", tags=["会议室预约"])


def _serialize(db: Session, reservations: list[Reservation]) -> list[dict]:
    if not reservations:
        return []
    venue_names = dict(
        db.execute(
            select(Venue.id, Venue.name).where(
                Venue.id.in_({item.venue_id for item in reservations})
            )
        ).all()
    )
    meeting_room_names = dict(
        db.execute(
            select(MeetingRoom.id, MeetingRoom.name).where(
                MeetingRoom.id.in_({item.meeting_room_id for item in reservations})
            )
        ).all()
    )
    user_ids = {item.user_id for item in reservations} | {
        item.reviewer_id for item in reservations if item.reviewer_id
    }
    users = {
        user.id: user
        for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    }

    return [
        reservation_to_dict(
            item,
            venue_names.get(item.venue_id, ""),
            meeting_room_names.get(item.meeting_room_id, ""),
            users.get(item.user_id),
            users.get(item.reviewer_id) if item.reviewer_id else None,
        )
        for item in reservations
    ]


@router.post("", response_model=ReservationOut, status_code=status.HTTP_201_CREATED)
def create_reservation_endpoint(
    payload: ReservationIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = create_reservation(db, current_user, payload)
    return _serialize(db, [reservation])[0]


@router.get("/my", response_model=Page[ReservationOut])
def list_my_reservations(
    status_filter: str = Query(default="", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = [Reservation.user_id == current_user.id]
    if status_filter:
        conditions.append(Reservation.status == status_filter)

    total = db.scalar(select(func.count(Reservation.id)).where(*conditions)) or 0
    reservations = db.scalars(
        select(Reservation)
        .where(*conditions)
        .order_by(Reservation.start_at.desc(), Reservation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    refresh_completed_status(db, list(reservations))
    return {
        "total": total,
        "items": _serialize(db, list(reservations)),
    }


@router.get("", response_model=Page[ReservationOut])
def list_reservations(
    status_filter: str = Query(default="", alias="status"),
    venue_id: int | None = Query(default=None),
    start_date: str = Query(default=""),
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    conditions = []
    if status_filter:
        conditions.append(Reservation.status == status_filter)
    if venue_id:
        conditions.append(Reservation.venue_id == venue_id)
    if start_date:
        try:
            day = datetime.fromisoformat(start_date).date()
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始日期格式不正确",
            ) from error
        conditions.append(func.date(Reservation.start_at) == day)
    if keyword:
        like = f"%{keyword.strip()}%"
        user_ids = select(User.id).where(
            or_(User.username.like(like), User.name.like(like))
        )
        conditions.append(Reservation.user_id.in_(user_ids))

    total = db.scalar(select(func.count(Reservation.id)).where(*conditions)) or 0
    reservations = db.scalars(
        select(Reservation)
        .where(*conditions)
        .order_by(
            case((Reservation.status == "pending", 0), else_=1),
            Reservation.start_at.desc(),
            Reservation.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    refresh_completed_status(db, list(reservations))
    return {
        "total": total,
        "items": _serialize(db, list(reservations)),
    }


@router.get("/{reservation_id}", response_model=ReservationOut)
def get_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    if (
        reservation.user_id != current_user.id
        and current_user.role != "admin"
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该预约")
    return _serialize(db, [reservation])[0]


@router.post("/{reservation_id}/review", response_model=ReservationOut)
def review_reservation(
    reservation_id: int,
    payload: ReservationReview,
    reviewer: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    if reservation.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该预约已处理，无法重复操作",
        )

    if payload.action == "confirm":
        meeting_room = db.get(MeetingRoom, reservation.meeting_room_id)
        if meeting_room is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会议室不存在")
        remaining = remaining_rooms(
            db,
            meeting_room,
            reservation.start_at,
            reservation.end_at,
            exclude_id=reservation.id,
        )
        if reservation.rooms > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"该会议室在预约时段内仅剩 {remaining} 间，无法确认",
            )
        reservation.status = "confirmed"
    else:
        reservation.status = "rejected"

    reservation.remark = payload.remark
    reservation.reviewer_id = reviewer.id
    reservation.reviewed_at = datetime.now()
    db.commit()
    db.refresh(reservation)
    return _serialize(db, [reservation])[0]


@router.post("/{reservation_id}/cancel", response_model=ReservationOut)
def cancel_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    if (
        reservation.user_id != current_user.id
        and current_user.role != "admin"
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该预约")
    if reservation.status not in ACTIVE_STATUS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前状态的预约无法取消",
        )

    reservation.status = "canceled"
    if current_user.role == "admin":
        reservation.remark = "管理员取消"
    db.commit()
    db.refresh(reservation)
    return _serialize(db, [reservation])[0]


@router.post("/{reservation_id}/finish", response_model=ReservationOut)
def finish_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提前结束使用中的预约，并立即释放剩余会议室库存。"""
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    if reservation.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该预约")
    if reservation.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有已确认的预约可以结束使用",
        )

    now = datetime.now()
    if now < reservation.start_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="预约尚未开始，如需取消请使用取消预约",
        )
    if now >= reservation.end_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="预约已到结束时间",
        )

    reservation.status = "completed"
    reservation.ended_at = now
    existing_remark = reservation.remark.strip()
    reservation.remark = f"{existing_remark}；提前结束" if existing_remark else "提前结束"
    db.commit()
    db.refresh(reservation)
    return _serialize(db, [reservation])[0]


@router.delete("/{reservation_id}", response_model=Message)
def delete_reservation(
    reservation_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    db.delete(reservation)
    db.commit()
    return Message(message="删除成功")
