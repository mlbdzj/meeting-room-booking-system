import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.reservation import confirm_draft
from app.agent.engine import answer_question
from app.agent.llm import resolve_provider
from app.agent.tools import TOOL_NAMES
from app.api.deps import get_current_user
from app.api.serializers import reservation_to_dict
from app.db.session import get_db
from app.models import ChatMessage, ChatSession, Knowledge, MeetingRoom, Reservation, User, Venue
from app.schemas.agent import (
    AgentStatus,
    ChatActionIn,
    ChatActionOut,
    ChatIn,
    ChatMessageOut,
    ChatReply,
    ChatSessionOut,
)
from app.schemas.common import Message

router = APIRouter(prefix="/api/agent", tags=["智能助手"])


def _get_session(db: Session, session_id: int, user: User) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    return session


def _get_message(db: Session, session_id: int, message_id: int, user: User) -> ChatMessage:
    session = _get_session(db, session_id, user)
    message = db.get(ChatMessage, message_id)
    if message is None or message.session_id != session.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")
    return message


def _load_action(message: ChatMessage) -> dict:
    try:
        action = json.loads(message.action or "{}")
    except json.JSONDecodeError:
        action = {}
    return action if isinstance(action, dict) else {}


def _save_action(message: ChatMessage, action: dict) -> None:
    message.action = json.dumps(action, ensure_ascii=False)


@router.get("/status", response_model=AgentStatus)
def agent_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    provider = resolve_provider()
    total = db.scalar(select(func.count(Knowledge.id)).where(Knowledge.status == 1)) or 0
    return AgentStatus(
        provider="llm" if provider else "local",
        model=provider["model"] if provider else "",
        llm_enabled=provider is not None,
        knowledge_total=total,
        tools=TOOL_NAMES,
    )


@router.get("/faq")
def quick_questions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entries = db.scalars(
        select(Knowledge).where(Knowledge.status == 1).order_by(Knowledge.id.asc()).limit(8)
    ).all()
    return [{"category": item.category, "question": item.question} for item in entries]


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .limit(20)
    ).all()


@router.post("/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = ChatSession(user_id=current_user.id, title="新的对话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_session(db, session_id, current_user).messages


@router.delete("/sessions/{session_id}", response_model=Message)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, current_user)
    db.delete(session)
    db.commit()
    return Message(message="已删除该对话")


@router.post("/chat", response_model=ChatReply)
def chat(payload: ChatIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    question = payload.message.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入问题内容")

    if payload.session_id:
        session = _get_session(db, payload.session_id, current_user)
    else:
        session = ChatSession(user_id=current_user.id, title=question[:20])
        db.add(session)
        db.commit()
        db.refresh(session)

    history = list(session.messages)
    db.add(ChatMessage(session_id=session.id, role="user", content=question))
    session.updated_at = datetime.now()
    db.commit()

    result = answer_question(db, current_user, question, history)

    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=result["content"],
        source=result.get("source", "local"),
        tools=",".join(result.get("tools", [])),
        action=json.dumps(result["action"], ensure_ascii=False) if result.get("action") else None,
    )
    db.add(assistant_message)
    if session.title in {"", "新的对话"}:
        session.title = question[:20]
    session.updated_at = datetime.now()
    db.commit()
    db.refresh(assistant_message)

    return ChatReply(
        session_id=session.id,
        reply=ChatMessageOut.model_validate(assistant_message),
        suggestions=result.get("suggestions", []),
        provider=result.get("source", "local"),
        action=result.get("action"),
    )


@router.post("/actions/confirm", response_model=ChatActionOut)
def confirm_action(
    payload: ChatActionIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户点击「确认预约」后真正创建预约。"""
    session = _get_session(db, payload.session_id, current_user)
    message = _get_message(db, payload.session_id, payload.message_id, current_user)
    action = _load_action(message)

    if action.get("type") != "reservation_draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这条消息没有可确认的操作")
    # 信息不全的草稿状态是 invalid，先给出具体缺什么，避免只提示「已处理」让人无从下手
    if action.get("problems"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="预约信息还不完整：" + "；".join(action["problems"]),
        )
    if action.get("status") != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该操作已经处理过了")

    try:
        reservation = confirm_draft(db, current_user, action)
    except HTTPException as error:
        action["status"] = "failed"
        action["error"] = str(error.detail)
        _save_action(message, action)
        db.commit()
        raise

    action["status"] = "confirmed"
    action["reservation_id"] = reservation.id
    action["error"] = ""
    _save_action(message, action)

    venue = db.get(Venue, reservation.venue_id)
    meeting_room = db.get(MeetingRoom, reservation.meeting_room_id)
    content = (
        f"预约已提交：{venue.name if venue else ''} {meeting_room.name if meeting_room else ''}，"
        f"{reservation.start_at:%Y-%m-%d %H:%M} 至 {reservation.end_at:%Y-%m-%d %H:%M}"
        f"（{float(reservation.hours or 0):g} 小时，{reservation.rooms} 间 / {reservation.attendees} 人），"
        f"总价 ¥{float(reservation.total_amount or 0):.0f}，当前状态为「待确认」。\n"
        "可以在「我的预约」页面查看确认进度。"
    )
    reply = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=content,
        source="system",
        tools="confirm_reservation",
    )
    db.add(reply)
    session.updated_at = datetime.now()
    db.commit()
    db.refresh(reply)

    return ChatActionOut(
        action=action,
        message=ChatMessageOut.model_validate(reply),
        reservation=reservation_to_dict(
            reservation,
            venue.name if venue else "",
            meeting_room.name if meeting_room else "",
            current_user,
        ),
    )


@router.post("/actions/cancel", response_model=ChatActionOut)
def cancel_action(
    payload: ChatActionIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用户放弃这次预约草稿。"""
    session = _get_session(db, payload.session_id, current_user)
    message = _get_message(db, payload.session_id, payload.message_id, current_user)
    action = _load_action(message)

    if action.get("status") == "pending":
        action["status"] = "canceled"
        _save_action(message, action)

    reply = ChatMessage(
        session_id=session.id,
        role="assistant",
        content="好的，这次预约没有提交。需要的话可以重新告诉我空间、日期时间和会议室。",
        source="system",
        tools="cancel_reservation",
    )
    db.add(reply)
    session.updated_at = datetime.now()
    db.commit()
    db.refresh(reply)

    return ChatActionOut(
        action=action, message=ChatMessageOut.model_validate(reply), reservation=None
    )
