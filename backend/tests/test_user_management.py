"""会员删除：同步清理关联的预约与对话，且不允许删除当前登录账号。

回归背景：删除会员时若只删 sys_user，会因 reservation.user_id / chat_session.user_id
存在外键引用而失败；本文件锁定「级联清理」这一行为。
"""

from sqlalchemy import select

from app.models import Reservation, ChatMessage, ChatSession, User
from helpers import reservation_payload


def test_admin_cannot_delete_self(client, seed, admin_headers):
    response = client.delete(f"/api/users/{seed.admin.id}", headers=admin_headers)
    assert response.status_code == 400
    assert "不能删除当前登录账号" in response.json()["detail"]


def test_admin_can_delete_member_with_related_records(client, seed, db, admin_headers, member_headers):
    # 该会员先产生一条预约，并通过助手发起一次对话（产生会话与消息）
    client.post("/api/reservations", json=reservation_payload(seed.venue, seed.king), headers=member_headers)
    client.post("/api/agent/chat", json={"message": "使用开始时间是几点？"}, headers=member_headers)

    session = db.scalars(select(ChatSession).where(ChatSession.user_id == seed.member.id)).first()
    assert session is not None
    session_id = session.id

    response = client.delete(f"/api/users/{seed.member.id}", headers=admin_headers)
    assert response.status_code == 200

    # 会员本体、其预约、其对话（含消息）都应被清理，不留悬挂外键
    assert db.get(User, seed.member.id) is None
    assert list(db.scalars(select(Reservation).where(Reservation.user_id == seed.member.id))) == []
    assert list(db.scalars(select(ChatSession).where(ChatSession.user_id == seed.member.id))) == []
    assert list(db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id))) == []
