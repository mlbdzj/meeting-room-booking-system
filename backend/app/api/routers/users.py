from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Reservation, User
from app.schemas.common import Message, Page
from app.schemas.user import PasswordUpdate, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["用户管理"], dependencies=[Depends(require_admin)])


@router.get("", response_model=Page[UserOut])
def list_users(
    keyword: str = Query(default=""),
    role: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    conditions = []
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(
            or_(User.username.like(like), User.name.like(like), User.phone.like(like))
        )
    if role:
        conditions.append(User.role == role)

    total = db.scalar(select(func.count(User.id)).where(*conditions)) or 0
    items = db.scalars(
        select(User)
        .where(*conditions)
        .order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"total": total, "items": [UserOut.model_validate(item) for item in items]}


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该账号已存在")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        name=payload.name or payload.username,
        phone=payload.phone,
        email=payload.email,
        role=payload.role,
        status=payload.status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if user.id == current_user.id and (payload.role != "admin" or payload.status != 1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改自己的角色或禁用自己")

    user.name = payload.name or user.username
    user.phone = payload.phone
    user.email = payload.email
    user.role = payload.role
    user.status = payload.status
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/password", response_model=Message)
def reset_password(user_id: int, payload: PasswordUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return Message(message="密码重置成功")


@router.delete("/{user_id}", response_model=Message)
def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录账号")

    # 同步清理该用户的预约记录，避免外键约束导致删除失败
    reservations = db.scalars(
        select(Reservation)
        .options(selectinload(Reservation.meeting_rooms))
        .where(Reservation.user_id == user_id)
    ).all()
    for reservation in reservations:
        reservation.meeting_rooms = []
        db.delete(reservation)

    db.delete(user)
    db.commit()
    return Message(message="删除成功")
