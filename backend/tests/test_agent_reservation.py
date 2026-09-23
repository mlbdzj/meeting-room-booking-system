"""自然语言预约链路：口语解析、草稿不落库、确认幂等与本地引擎降级。"""

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.agent.reservation import build_draft, cn_to_int, parse_attendees, parse_hours, parse_rooms, prepare_from_text
from app.models import Reservation, ChatMessage, ChatSession
from helpers import seed_reservation


@pytest.fixture
def chat_session(db, seed):
    session = ChatSession(user_id=seed.member.id, title="测试会话")
    db.add(session)
    db.commit()
    return session


def _draft_message(db, session, draft, content="（助手）这是为你准备的预约预览"):
    message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=content,
        source="local",
        tools="prepare_reservation",
        action=json.dumps(draft, ensure_ascii=False),
    )
    db.add(message)
    db.commit()
    return message


def _reservation_count(db) -> int:
    return db.scalar(select(func.count(Reservation.id))) or 0


# ---------- 中文数字与口语解析 ----------


@pytest.mark.parametrize(
    "text, expected",
    [("两", 2), ("二", 2), ("十", 10), ("十二", 12), ("二十", 20), ("3", 3), ("10", 10)],
)
def test_cn_to_int(text, expected):
    assert cn_to_int(text) == expected


def test_cn_to_int_returns_none_for_unparsable():
    assert cn_to_int("") is None
    assert cn_to_int("很多") is None


@pytest.mark.parametrize(
    "text, expected",
    [("住两晚", 2), ("住 3 晚", 3), ("共五晚", 5), ("连住十二晚", 12), ("今晚", None)],
)
def test_parse_hours(text, expected):
    assert parse_hours(text) == expected


@pytest.mark.parametrize("text, expected", [("两间", 2), ("3 间", 3), ("要一间大床房", 1), ("没有", None)])
def test_parse_rooms(text, expected):
    assert parse_rooms(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [("2 个人", 2), ("两位客人", 2), ("3名成人", 3), ("四位", None)],
)
def test_parse_attendees(text, expected):
    assert parse_attendees(text) == expected


def test_draft_from_sentence_parses_all_fields(db, seed):
    """一句口语描述要能解析出会议空间、会议室类型、日期、晚数、间数、人数与特殊要求。"""
    draft = prepare_from_text(
        db, seed.member, "下周五使用开始两晚的杭州西湖智选假日会议空间高级大床房，两间，4 个人，需要安静楼层"
    )
    payload = draft["payload"]

    assert payload["venue_id"] == seed.venue.id
    assert payload["meeting_room_id"] == seed.king.id
    assert payload["hours"] == 2
    assert payload["rooms"] == 2
    assert payload["attendees"] == 4
    # 「需要」属于语气词，会在解析特殊要求时被剔除
    assert payload["equipment_request"] == "安静楼层"
    assert date.fromisoformat(payload["start_at"]) >= date.today()
    assert (
        date.fromisoformat(payload["end_at"]) - date.fromisoformat(payload["start_at"])
    ).days == 2
    assert draft["status"] == "pending"
    assert draft["problems"] == []


def test_draft_matches_venue_short_name(db, seed):
    draft = prepare_from_text(db, seed.member, "下周三使用开始一晚的杭州西湖智选的双床房，2 个人")
    assert draft["payload"]["venue_id"] == seed.venue.id
    assert draft["payload"]["meeting_room_id"] == seed.twin.id


def test_draft_uses_single_night_when_not_mentioned(db, seed):
    draft = prepare_from_text(db, seed.member, "明天使用开始杭州西湖智选假日会议空间高级大床房，2 个人")
    assert draft["payload"]["hours"] == 1
    assert draft["note"]


def test_draft_reports_missing_fields(db, seed):
    draft = prepare_from_text(db, seed.member, "帮我订个房")
    assert draft["status"] == "invalid"
    assert any("会议空间" in item for item in draft["problems"])
    assert any("会议室类型" in item for item in draft["problems"])
    assert any("日期" in item for item in draft["problems"])


def test_draft_detects_oversell(db, seed):
    seed_reservation(db, user=seed.stranger, venue=seed.venue, meeting_room=seed.twin, rooms=1, days_from=7, hours=2)
    check_in = date.today() + timedelta(days=7)
    draft = build_draft(
        db,
        seed.member,
        venue=seed.venue,
        venue_name=seed.venue.name,
        meeting_room=seed.twin,
        start_at=check_in,
        end_at=check_in + timedelta(days=2),
        rooms=1,
        attendees=2,
    )
    assert draft["status"] == "invalid"
    assert any("仅剩 0 间可订" in item for item in draft["problems"])


def test_draft_never_writes_to_database(db, seed):
    before = _reservation_count(db)
    draft = prepare_from_text(db, seed.member, "下周五使用开始两晚的杭州西湖智选假日会议空间高级大床房，2 个人")
    assert draft["status"] == "pending"
    assert _reservation_count(db) == before


# ---------- 确认 / 取消草稿 ----------


def _confirm(client, session, message, headers):
    return client.post(
        "/api/agent/actions/confirm",
        json={"session_id": session.id, "message_id": message.id},
        headers=headers,
    )


def test_confirm_draft_creates_pending_reservation(client, db, seed, member_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "下周五使用开始两晚的杭州西湖智选假日会议空间高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["action"]["status"] == "confirmed"
    assert body["reservation"]["status"] == "pending"
    assert body["reservation"]["user_id"] == seed.member.id
    assert body["reservation"]["total_amount"] == draft["payload"]["total_amount"]
    assert "预约已提交" in body["message"]["content"]

    saved = db.get(Reservation, body["reservation"]["id"])
    assert saved is not None
    assert saved.rooms == draft["payload"]["rooms"]


def test_confirm_draft_is_idempotent(client, db, seed, member_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "下周五使用开始两晚的杭州西湖智选假日会议空间高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    first = _confirm(client, chat_session, message, member_headers)
    assert first.status_code == 200
    count_after_first = _reservation_count(db)

    second = _confirm(client, chat_session, message, member_headers)
    assert second.status_code == 400
    assert second.json()["detail"] == "该操作已经处理过了"
    assert _reservation_count(db) == count_after_first


def test_confirm_rejects_draft_with_problems(client, db, seed, member_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "帮我订个房")
    message = _draft_message(db, chat_session, draft)

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert "预约信息还不完整" in response.json()["detail"]
    assert _reservation_count(db) == 0


def test_confirm_marks_draft_failed_when_inventory_changed(client, db, seed, member_headers, chat_session):
    """草稿生成后会议室余量被抢光：确认时二次校验失败，草稿标记为 failed。"""
    draft = prepare_from_text(db, seed.member, "下周五使用开始两晚的杭州西湖智选假日会议空间高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    payload = draft["payload"]
    check_in = date.fromisoformat(payload["start_at"])
    seed_reservation(
        db,
        user=seed.stranger,
        venue=seed.venue,
        meeting_room=seed.king,
        rooms=3,
        days_from=(check_in - date.today()).days,
        hours=payload["hours"],
    )

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert "仅剩 0 间可订" in response.json()["detail"]

    stored = json.loads(db.get(ChatMessage, message.id).action)
    assert stored["status"] == "failed"
    assert "仅剩 0 间可订" in stored["error"]


def test_cancelled_draft_cannot_be_confirmed(client, db, seed, member_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "下周五使用开始两晚的杭州西湖智选假日会议空间高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    cancel = client.post(
        "/api/agent/actions/cancel",
        json={"session_id": chat_session.id, "message_id": message.id},
        headers=member_headers,
    )
    assert cancel.status_code == 200
    assert cancel.json()["action"]["status"] == "canceled"

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert _reservation_count(db) == 0


def test_other_user_cannot_confirm_someone_elses_draft(client, db, seed, stranger_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "下周五使用开始两晚的杭州西湖智选假日会议空间高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    response = _confirm(client, chat_session, message, stranger_headers)
    assert response.status_code == 404
    assert "对话不存在" in response.json()["detail"]


def test_confirm_rejects_message_without_action(client, db, seed, member_headers, chat_session):
    message = ChatMessage(
        session_id=chat_session.id, role="assistant", content="使用开始时间是 14:00 之后。", source="local"
    )
    db.add(message)
    db.commit()

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert "没有可确认的操作" in response.json()["detail"]


# ---------- 本地知识库引擎（降级路径） ----------


def test_local_engine_answers_from_knowledge_base(client, seed, member_headers):
    response = client.post(
        "/api/agent/chat", json={"message": "请问使用开始和使用结束时间是几点？"}, headers=member_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local"
    assert "14:00" in body["reply"]["content"]


def test_agent_status_reports_local_provider_and_tools(client, member_headers):
    response = client.get("/api/agent/status", headers=member_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local"
    assert body["llm_enabled"] is False
    assert body["knowledge_total"] == 1
    assert len(body["tools"]) == 8
