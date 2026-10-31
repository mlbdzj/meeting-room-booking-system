"""权限隔离：接口鉴权、角色边界、数据范围与确认阶段二次校验。"""

from helpers import auth_headers, reservation_payload, seed_reservation


def test_protected_endpoints_require_login(client):
    for method, path in [
        ("get", "/api/reservations"),
        ("get", "/api/reservations/my"),
        ("get", "/api/stats/overview"),
        ("get", "/api/agent/status"),
        ("get", "/api/users"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, path
        assert response.json()["detail"] == "请先登录"


def test_forged_token_is_rejected(client, seed):
    headers = {"Authorization": "Bearer forged.payload"}
    assert client.get("/api/reservations/my", headers=headers).status_code == 401
    assert client.get("/api/stats/overview", headers=headers).status_code == 401


def test_disabled_account_cannot_use_token(client, seed):
    seed.stranger.status = 0
    response = client.get(
        "/api/reservations/my", headers=auth_headers(seed.stranger)
    )
    assert response.status_code == 403
    assert "账号已被禁用" in response.json()["detail"]


def test_member_cannot_list_all_reservations(client, seed, member_headers):
    response = client.get("/api/reservations", headers=member_headers)
    assert response.status_code == 403
    assert "仅管理员可操作" in response.json()["detail"]


def test_member_cannot_review_reservation(
    client, seed, member_headers
):
    created = client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom),
        headers=member_headers,
    ).json()
    response = client.post(
        f"/api/reservations/{created['id']}/review",
        json={"action": "confirm", "remark": ""},
        headers=member_headers,
    )
    assert response.status_code == 403


def test_member_cannot_delete_reservation(
    client, seed, member_headers
):
    created = client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom),
        headers=member_headers,
    ).json()
    response = client.delete(
        f"/api/reservations/{created['id']}", headers=member_headers
    )
    assert response.status_code == 403


def test_member_cannot_read_others_reservation(
    client, seed, member_headers, stranger_headers
):
    other = client.post(
        "/api/reservations",
        json=reservation_payload(
            seed.venue,
            seed.boardroom,
            days_from=10,
        ),
        headers=stranger_headers,
    ).json()
    response = client.get(
        f"/api/reservations/{other['id']}", headers=member_headers
    )
    assert response.status_code == 403
    assert "无权查看该预约" in response.json()["detail"]


def test_member_cannot_cancel_others_reservation(
    client, seed, member_headers, stranger_headers
):
    other = client.post(
        "/api/reservations",
        json=reservation_payload(
            seed.venue,
            seed.boardroom,
            days_from=10,
        ),
        headers=stranger_headers,
    ).json()
    response = client.post(
        f"/api/reservations/{other['id']}/cancel",
        headers=member_headers,
    )
    assert response.status_code == 403


def test_member_can_cancel_own_reservation(
    client, seed, member_headers
):
    created = client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom),
        headers=member_headers,
    ).json()
    response = client.post(
        f"/api/reservations/{created['id']}/cancel",
        headers=member_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"


def test_cancel_is_rejected_for_already_canceled_reservation(
    client, seed, member_headers
):
    created = client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom),
        headers=member_headers,
    ).json()
    client.post(
        f"/api/reservations/{created['id']}/cancel",
        headers=member_headers,
    )
    again = client.post(
        f"/api/reservations/{created['id']}/cancel",
        headers=member_headers,
    )
    assert again.status_code == 400
    assert "无法取消" in again.json()["detail"]


def test_member_cannot_manage_users_and_knowledge(
    client, seed, member_headers
):
    assert client.get("/api/users", headers=member_headers).status_code == 403
    assert (
        client.post(
            "/api/knowledge",
            json={
                "category": "测试",
                "question": "问题",
                "answer": "答案",
                "keywords": "",
            },
            headers=member_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/meeting-rooms",
            json={
                "venue_id": seed.venue.id,
                "name": "越权会议室",
                "code": "X1",
                "layout": "U 型",
                "hourly_price": 100,
                "capacity": 6,
                "quantity": 1,
                "equipment": "",
                "status": "open",
            },
            headers=member_headers,
        ).status_code
        == 403
    )


def test_admin_sees_all_reservations_and_member_sees_own(
    client, seed, admin_headers, member_headers, stranger_headers
):
    client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom, days_from=7),
        headers=member_headers,
    )
    client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom, days_from=10),
        headers=stranger_headers,
    )
    client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.small, days_from=12),
        headers=stranger_headers,
    )

    admin_view = client.get(
        "/api/reservations", headers=admin_headers
    ).json()
    member_view = client.get(
        "/api/reservations/my", headers=member_headers
    ).json()

    assert admin_view["total"] == 3
    assert member_view["total"] == 1
    assert all(
        item["username"] == "student" for item in member_view["items"]
    )


def test_admin_can_filter_reservations_by_status(
    client, seed, admin_headers, member_headers
):
    pending = client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom, days_from=7),
        headers=member_headers,
    ).json()
    confirmed = client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.small, days_from=20),
        headers=member_headers,
    ).json()
    client.post(
        f"/api/reservations/{confirmed['id']}/review",
        json={"action": "confirm", "remark": ""},
        headers=admin_headers,
    )

    only_pending = client.get(
        "/api/reservations",
        params={"status": "pending"},
        headers=admin_headers,
    ).json()
    assert [item["id"] for item in only_pending["items"]] == [pending["id"]]

    only_confirmed = client.get(
        "/api/reservations",
        params={"status": "confirmed"},
        headers=admin_headers,
    ).json()
    assert [item["id"] for item in only_confirmed["items"]] == [
        confirmed["id"]
    ]


def test_admin_review_confirms_reservation(
    client, seed, admin_headers, member_headers
):
    created = client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom),
        headers=member_headers,
    ).json()
    response = client.post(
        f"/api/reservations/{created['id']}/review",
        json={"action": "confirm", "remark": "已确认，会议室已保留"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["remark"] == "已确认，会议室已保留"
    assert body["reviewer_name"] == seed.admin.name
    assert body["reviewed_at"] is not None


def test_admin_review_rejects_reservation(
    client, seed, admin_headers, member_headers
):
    created = client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom),
        headers=member_headers,
    ).json()
    response = client.post(
        f"/api/reservations/{created['id']}/review",
        json={"action": "reject", "remark": "该时段会议室紧张"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_review_twice_is_rejected(
    client, seed, admin_headers, member_headers
):
    created = client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom),
        headers=member_headers,
    ).json()
    payload = {"action": "confirm", "remark": ""}
    assert (
        client.post(
            f"/api/reservations/{created['id']}/review",
            json=payload,
            headers=admin_headers,
        ).status_code
        == 200
    )
    again = client.post(
        f"/api/reservations/{created['id']}/review",
        json=payload,
        headers=admin_headers,
    )
    assert again.status_code == 400
    assert "已处理" in again.json()["detail"]


def test_review_revalidates_inventory(
    client, seed, db, admin_headers
):
    """两条待确认预约争用唯一会议室时，确认阶段二次校验。"""
    first = seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.small,
        rooms=1,
    )
    second = seed_reservation(
        db,
        user=seed.stranger,
        venue=seed.venue,
        meeting_room=seed.small,
        rooms=1,
    )

    blocked = client.post(
        f"/api/reservations/{first.id}/review",
        json={"action": "confirm", "remark": ""},
        headers=admin_headers,
    )
    assert blocked.status_code == 400
    assert "仅剩 0 间" in blocked.json()["detail"]

    assert (
        client.post(
            f"/api/reservations/{second.id}/cancel",
            headers=admin_headers,
        ).status_code
        == 200
    )
    ok = client.post(
        f"/api/reservations/{first.id}/review",
        json={"action": "confirm", "remark": ""},
        headers=admin_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "confirmed"


def test_member_stats_are_scoped_to_own_reservations(
    client, seed, admin_headers, member_headers, stranger_headers
):
    client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom, days_from=7),
        headers=member_headers,
    )
    client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.boardroom, days_from=10),
        headers=stranger_headers,
    )
    client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.small, days_from=12),
        headers=stranger_headers,
    )

    admin_view = client.get(
        "/api/stats/overview", headers=admin_headers
    ).json()
    member_view = client.get(
        "/api/stats/overview", headers=member_headers
    ).json()

    assert admin_view["reservation_total"] == 3
    assert member_view["reservation_total"] == 1
    assert len(member_view["recent_reservations"]) == 1
    assert member_view["venue_total"] == admin_view["venue_total"]


def test_agent_tools_follow_user_role(
    client, seed, admin_headers, member_headers
):
    member_reply = client.post(
        "/api/agent/chat",
        json={"message": "有哪些待确认预约？"},
        headers=member_headers,
    ).json()
    admin_reply = client.post(
        "/api/agent/chat",
        json={"message": "有哪些待确认预约？"},
        headers=admin_headers,
    ).json()

    assert member_reply["reply"]["content"] != admin_reply["reply"]["content"]
    assert "管理员" in member_reply["reply"]["content"]
