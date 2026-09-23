from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models import Knowledge, User
from app.schemas.agent import KnowledgeIn, KnowledgeOut
from app.schemas.common import Message, Page

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.get("", response_model=Page[KnowledgeOut])
def list_knowledge(
    keyword: str = Query(default=""),
    category: str = Query(default=""),
    status_filter: int | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = []
    if current_user.role != "admin":
        conditions.append(Knowledge.status == 1)
    elif status_filter is not None:
        conditions.append(Knowledge.status == status_filter)
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(
            or_(Knowledge.question.like(like), Knowledge.answer.like(like), Knowledge.keywords.like(like))
        )
    if category:
        conditions.append(Knowledge.category == category)

    total = db.scalar(select(func.count(Knowledge.id)).where(*conditions)) or 0
    items = db.scalars(
        select(Knowledge)
        .where(*conditions)
        .order_by(Knowledge.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"total": total, "items": items}


@router.get("/categories", response_model=list[str])
def list_categories(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Knowledge.category).distinct().order_by(Knowledge.category)).all()
    return [item for item in rows if item]


@router.post("", response_model=KnowledgeOut, status_code=status.HTTP_201_CREATED)
def create_knowledge(payload: KnowledgeIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    entry = Knowledge(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/{entry_id}", response_model=KnowledgeOut)
def update_knowledge(
    entry_id: int,
    payload: KnowledgeIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    entry = db.get(Knowledge, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识条目不存在")
    for field, value in payload.model_dump().items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", response_model=Message)
def delete_knowledge(entry_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    entry = db.get(Knowledge, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识条目不存在")
    db.delete(entry)
    db.commit()
    return Message(message="删除成功")
