"""下单接口：参数校验、库存拦截、价格结算与会议室状态查询。"""

from datetime import date, timedelta

from helpers import reservation_payload


def _in(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def test_create_reservation_returns_201_with_server_side_total(client, seed, member_headers):
    payload = reservation_payload(seed.venue, seed.king, days_from=7, hours=2, rooms=2, attendees=4)
    response = client.post("/api/reservations", json=payload, headers=member_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["status_text"] == "待确认"
    assert body["hours"] == 2
    # 458 × 2 晚 × 2 间
    assert body["total_amount"] == 1832.0
    assert body["user_id"] == seed.member.id
    assert body["venue_name"] == seed.venue.name


def test_create_reservation_ignores_client_supplied_price(client, seed, member_headers):
    """金额与晚数由服务端推导，前端多传的字段被忽略。"""
    payload = reservation_payload(seed.venue, seed.king, days_from=7, hours=2)
    payload.update({"total_amount": 1, "hours": 99, "status": "confirmed", "user_id": 999})
    response = client.post("/api/reservations", json=payload, headers=member_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["total_amount"] == 916.0
    assert body["hours"] == 2
    assert body["status"] == "pending"
    assert body["user_id"] == seed.member.id


def test_create_reservation_rejects_check_in_before_today(client, seed, member_headers):
    payload = reservation_payload(seed.venue, seed.king, days_from=-1, hours=2)
    response = client.post("/api/reservations", json=payload, headers=member_headers)

    assert response.status_code == 400
    assert "使用开始日期不能早于今天" in response.json()["detail"]


def test_create_reservation_rejects_check_out_not_after_check_in(client, seed, member_headers):
    payload = reservation_payload(seed.venue, seed.king, days_from=7, hours=0)
    response = client.post("/api/reservations", json=payload, headers=member_headers)

    assert response.status_code == 422
    assert "使用结束日期必须晚于使用开始日期" in response.json()["detail"]


def test_create_reservation_rejects_oversell(client, seed, member_headers):
    """双床房只剩 0 间时必须拒单，且提示剩余数量。"""
    first = client.post(
        "/api/reservations", json=reservation_payload(seed.venue, seed.twin, days_from=30, hours=2), headers=member_headers
    )
    assert first.status_code == 201

    second = client.post(
        "/api/reservations", json=reservation_payload(seed.venue, seed.twin, days_from=30, hours=2), headers=member_headers
    )
    assert second.status_code == 400
    assert "仅剩 0 间可订" in second.json()["detail"]


def test_adjacent_stay_is_not_blocked(client, seed, member_headers):
    """上一单使用结束当天可以使用开始：区间是左闭右开的。"""
    assert (
        client.post(
            "/api/reservations", json=reservation_payload(seed.venue, seed.twin, days_from=7, hours=2), headers=member_headers
        ).status_code
        == 201
    )
    adjacent = client.post(
        "/api/reservations", json=reservation_payload(seed.venue, seed.twin, days_from=9, hours=2), headers=member_headers
    )
    assert adjacent.status_code == 201


def test_cancelled_reservation_releases_inventory(client, seed, member_headers):
    first = client.post(
        "/api/reservations", json=reservation_payload(seed.venue, seed.twin, days_from=7, hours=2), headers=member_headers
    )
    assert first.status_code == 201
    assert (
        client.post(
            "/api/reservations", json=reservation_payload(seed.venue, seed.twin, days_from=7, hours=2), headers=member_headers
        ).status_code
        == 400
    )

    assert client.post(f"/api/reservations/{first.json()['id']}/cancel", headers=member_headers).status_code == 200

    retry = client.post(
        "/api/reservations", json=reservation_payload(seed.venue, seed.twin, days_from=7, hours=2), headers=member_headers
    )
    assert retry.status_code == 201


def test_my_reservations_returns_only_own_records(client, seed, member_headers, stranger_headers):
    mine = client.post(
        "/api/reservations", json=reservation_payload(seed.venue, seed.king, days_from=7, hours=2), headers=member_headers
    ).json()
    client.post(
        "/api/reservations",
        json=reservation_payload(seed.venue, seed.king, days_from=20, hours=1),
        headers=stranger_headers,
    )

    response = client.get("/api/reservations/my", headers=member_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [mine["id"]]


def test_availability_reports_remaining_and_bookable(client, seed, member_headers):
    client.post(
        "/api/reservations", json=reservation_payload(seed.venue, seed.twin, days_from=7, hours=2), headers=member_headers
    )

    response = client.get(
        f"/api/venues/{seed.venue.id}/availability",
        params={"check_in": _in(7), "check_out": _in(9)},
        headers=member_headers,
    )
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["meeting_rooms"]}

    twin = items[seed.twin.id]
    assert twin["quantity"] == 1
    assert twin["remaining"] == 0
    assert twin["bookable"] is False

    king = items[seed.king.id]
    assert king["remaining"] == 3
    assert king["bookable"] is True

    maintenance = items[seed.maintenance.id]
    assert maintenance["remaining"] == 2
    assert maintenance["bookable"] is False


def test_availability_rejects_reversed_range(client, seed, member_headers):
    response = client.get(
        f"/api/venues/{seed.venue.id}/availability",
        params={"check_in": _in(9), "check_out": _in(7)},
        headers=member_headers,
    )
    assert response.status_code == 400
    assert "使用结束日期必须晚于使用开始日期" in response.json()["detail"]


def test_availability_returns_404_for_unknown_venue(client, seed, member_headers):
    response = client.get(
        "/api/venues/9999/availability",
        params={"check_in": _in(7), "check_out": _in(9)},
        headers=member_headers,
    )
    assert response.status_code == 404
