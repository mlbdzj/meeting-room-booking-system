"""Agent 预约链路：口语解析、草稿不落库、确认幂等与本地降级。"""

import json
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.agent.reservation import (
    build_draft,
    cn_to_int,
    parse_attendees,
    parse_hours,
    parse_reservation_text,
    parse_rooms,
    prepare_from_text,
)
from app.models import ChatMessage, ChatSession, Reservation
from helpers import seed_reservation, slot


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


@pytest.mark.parametrize(
    "text, expected",
    [
        ("两", 2),
        ("二", 2),
        ("十", 10),
        ("十二", 12),
        ("二十", 20),
        ("3", 3),
        ("10", 10),
    ],
)
def test_cn_to_int(text, expected):
    assert cn_to_int(text) == expected


def test_cn_to_int_returns_none_for_unparsable():
    assert cn_to_int("") is None
    assert cn_to_int("很多") is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("使用两小时", 2),
        ("2.5小时", 2.5),
        ("一个半小时", 1.5),
        ("半小时", 0.5),
        ("90分钟", 1.5),
        ("半天", 4),
        ("全天", 8),
    ],
)
def test_parse_hours(text, expected):
    assert parse_hours(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [("两间", 2), ("3 间", 3), ("要一间会议室", 1), ("没有", None)],
)
def test_parse_rooms(text, expected):
    assert parse_rooms(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2 个人", 2),
        ("两位参会人员", 2),
        ("3名客人", 3),
        ("四位", None),
    ],
)
def test_parse_attendees(text, expected):
    assert parse_attendees(text) == expected


def test_parse_sentence_extracts_time_and_capacity(db, seed):
    parsed = parse_reservation_text(
        db,
        "下周五上午10点到12点的杭州西湖商务中心西湖 A 会议室，10人",
    )
    assert parsed["venue_id"] if "venue_id" in parsed else parsed["venue"].id == seed.venue.id
    assert parsed["meeting_room"].id == seed.boardroom.id
    assert parsed["start_at"].hour == 10
    assert parsed["end_at"].hour == 12
    assert parsed["hours"] == 2.0
    assert parsed["attendees"] == 10
    assert parsed["start_at"].date() >= date.today()


def test_draft_from_sentence_parses_all_fields(db, seed):
    draft = prepare_from_text(
        db,
        seed.member,
        "下周五上午10点到12点订杭州西湖商务中心西湖 A 会议室，两间，10人，需要视频会议",
    )
    payload = draft["payload"]

    assert payload["venue_id"] == seed.venue.id
    assert payload["meeting_room_id"] == seed.boardroom.id
    assert payload["hours"] == 2.0
    assert payload["rooms"] == 2
    assert payload["attendees"] == 10
    assert payload["equipment_request"] == "视频会议"
    assert payload["total_amount"] == 480.0
    assert draft["type"] == "reservation_draft"
    assert draft["status"] == "pending"
    assert draft["problems"] == []


def test_draft_matches_venue_short_name(db, seed):
    draft = prepare_from_text(
        db,
        seed.member,
        "明天下午2点到4点的杭州西湖西湖 B 会议室，2 个人",
    )
    assert draft["payload"]["venue_id"] == seed.venue.id
    assert draft["payload"]["meeting_room_id"] == seed.small.id


def test_draft_reports_missing_fields(db, seed):
    draft = prepare_from_text(db, seed.member, "帮我预约个会议室")
    assert draft["status"] == "invalid"
    assert any("会议空间" in item for item in draft["problems"])
    assert any("会议室" in item for item in draft["problems"])
    assert any("开始日期" in item for item in draft["problems"])
    assert any("参会人数" in item for item in draft["problems"])


def test_draft_detects_oversell(db, seed):
    seed_reservation(
        db,
        user=seed.stranger,
        venue=seed.venue,
        meeting_room=seed.small,
        rooms=1,
    )
    start_at, end_at = slot(days_from=7)
    draft = build_draft(
        db,
        seed.member,
        venue=seed.venue,
        venue_name=seed.venue.name,
        meeting_room=seed.small,
        start_at=start_at,
        end_at=end_at,
        rooms=1,
        attendees=2,
    )
    assert draft["status"] == "invalid"
    assert any("仅剩 0 间可预约" in item for item in draft["problems"])


def test_draft_never_writes_to_database(db, seed):
    before = _reservation_count(db)
    draft = prepare_from_text(
        db,
        seed.member,
        "下周五上午10点到12点订杭州西湖商务中心西湖 A 会议室，10人",
    )
    assert draft["status"] == "pending"
    assert _reservation_count(db) == before


def _confirm(client, session, message, headers):
    return client.post(
        "/api/agent/actions/confirm",
        json={"session_id": session.id, "message_id": message.id},
        headers=headers,
    )


def test_confirm_draft_creates_pending_reservation(
    client, db, seed, member_headers, chat_session
):
    draft = prepare_from_text(
        db,
        seed.member,
        "下周五上午10点到12点订杭州西湖商务中心西湖 A 会议室，10人",
    )
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


def test_confirm_draft_is_idempotent(
    client, db, seed, member_headers, chat_session
):
    draft = prepare_from_text(
        db,
        seed.member,
        "下周五上午10点到12点订杭州西湖商务中心西湖 A 会议室，10人",
    )
    message = _draft_message(db, chat_session, draft)

    first = _confirm(client, chat_session, message, member_headers)
    assert first.status_code == 200
    count_after_first = _reservation_count(db)

    second = _confirm(client, chat_session, message, member_headers)
    assert second.status_code == 400
    assert second.json()["detail"] == "该操作已经处理过了"
    assert _reservation_count(db) == count_after_first


def test_confirm_rejects_draft_with_problems(
    client, db, seed, member_headers, chat_session
):
    draft = prepare_from_text(db, seed.member, "帮我预约个会议室")
    message = _draft_message(db, chat_session, draft)

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert "预约信息还不完整" in response.json()["detail"]
    assert _reservation_count(db) == 0


def test_confirm_marks_draft_failed_when_inventory_changed(
    client, db, seed, member_headers, chat_session
):
    draft = prepare_from_text(
        db,
        seed.member,
        "下周五上午10点到12点订杭州西湖商务中心西湖 A 会议室，10人",
    )
    message = _draft_message(db, chat_session, draft)

    payload = draft["payload"]
    start_at = datetime.fromisoformat(payload["start_at"])
    seed_reservation(
        db,
        user=seed.stranger,
        venue=seed.venue,
        meeting_room=seed.boardroom,
        rooms=3,
        days_from=(start_at.date() - date.today()).days,
        hour=start_at.hour,
        hours=payload["hours"],
    )

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert "仅剩 0 间可预约" in response.json()["detail"]

    stored = json.loads(db.get(ChatMessage, message.id).action)
    assert stored["status"] == "failed"
    assert "仅剩 0 间可预约" in stored["error"]


def test_cancelled_draft_cannot_be_confirmed(
    client, db, seed, member_headers, chat_session
):
    draft = prepare_from_text(
        db,
        seed.member,
        "下周五上午10点到12点订杭州西湖商务中心西湖 A 会议室，10人",
    )
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


def test_other_user_cannot_confirm_someone_elses_draft(
    client, db, seed, stranger_headers, chat_session
):
    draft = prepare_from_text(
        db,
        seed.member,
        "下周五上午10点到12点订杭州西湖商务中心西湖 A 会议室，10人",
    )
    message = _draft_message(db, chat_session, draft)

    response = _confirm(client, chat_session, message, stranger_headers)
    assert response.status_code == 404
    assert "对话不存在" in response.json()["detail"]


def test_confirm_rejects_message_without_action(
    client, db, seed, member_headers, chat_session
):
    message = ChatMessage(
        session_id=chat_session.id,
        role="assistant",
        content="开放时间是 08:30-20:00。",
        source="local",
    )
    db.add(message)
    db.commit()

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert "没有可确认的操作" in response.json()["detail"]


def test_local_engine_answers_from_knowledge_base(
    client, seed, member_headers
):
    response = client.post(
        "/api/agent/chat",
        json={"message": "会议空间开放时间是几点？"},
        headers=member_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local"
    assert "08:30-20:00" in body["reply"]["content"]


def test_agent_status_reports_local_provider_and_tools(
    client, member_headers
):
    response = client.get("/api/agent/status", headers=member_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local"
    assert body["llm_enabled"] is False
    assert body["knowledge_total"] == 1
    assert len(body["tools"]) == 8
    assert "prepare_reservation" in body["tools"]
