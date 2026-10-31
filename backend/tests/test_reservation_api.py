"""预约接口：参数校验、余量拦截、价格结算与会议室可用性。"""

from datetime import date, datetime, time, timedelta

from helpers import reservation_payload, slot


def _iso_days(days: int, hour: int = 10) -> str:
    return datetime.combine(
        date.today() + timedelta(days=days),
        time(hour, 0),
    ).isoformat()


def test_create_reservation_returns_201_with_server_side_total(
    client, seed, member_headers
):
    payload = reservation_payload(
        seed.venue,
        seed.boardroom,
        days_from=7,
        hours=2,
        rooms=2,
        attendees=20,
    )
    response = client.post("/api/reservations", json=payload, headers=member_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["status_text"] == "待确认"
    assert body["hours"] == 2.0
    assert body["total_amount"] == 480.0
    assert body["user_id"] == seed.member.id
    assert body["venue_name"] == seed.venue.name


def test_create_reservation_ignores_client_supplied_price(
    client, seed, member_headers
):
    payload = reservation_payload(
        seed.venue,
        seed.boardroom,
        days_from=7,
        hours=2,
    )
    payload.update(
        {
            "total_amount": 1,
            "hours": 99,
            "status": "confirmed",
            "user_id": 999,
        }
    )
    response = client.post("/api/reservations", json=payload, headers=member_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["total_amount"] == 240.0
    assert body["hours"] == 2.0
    assert body["status"] == "pending"
    assert body["user_id"] == seed.member.id


def test_create_reservation_rejects_past_start(client, seed, member_headers):
    payload = reservation_payload(
        seed.venue,
        seed.boardroom,
        days_from=-1,
    )
    response = client.post("/api/reservations", json=payload, headers=member_headers)

    assert response.status_code == 400
    assert "开始时间不能早于当前时间" in response.json()["detail"]


def test_create_reservation_rejects_reversed_time(client, seed, member_headers):
    start_at, _ = slot(days_from=7)
    payload = reservation_payload(seed.venue, seed.boardroom, days_from=7)
    payload["end_at"] = start_at.isoformat()
    response = client.post("/api/reservations", json=payload, headers=member_headers)

    assert response.status_code == 422
    assert "结束时间必须晚于开始时间" in response.json()["detail"]


def test_create_reservation_rejects_oversell(client, seed, member_headers):
    first = client.post(
        "/api/reservations",
        json=reservation_payload(
            seed.venue,
            seed.small,
            days_from=30,
            hours=2,
        ),
        headers=member_headers,
    )
    assert first.status_code == 201

    second = client.post(
        "/api/reservations",
        json=reservation_payload(
            seed.venue,
            seed.small,
            days_from=30,
            hours=2,
        ),
        headers=member_headers,
    )
    assert second.status_code == 400
    assert "仅剩 0 间可预约" in second.json()["detail"]


def test_adjacent_window_is_not_blocked(client, seed, member_headers):
    first = client.post(
        "/api/reservations",
        json=reservation_payload(
            seed.venue,
            seed.small,
            days_from=7,
            hour=10,
            hours=2,
        ),
        headers=member_headers,
    )
    assert first.status_code == 201

    adjacent = client.post(
        "/api/reservations",
        json=reservation_payload(
            seed.venue,
            seed.small,
            days_from=7,
            hour=12,
            hours=2,
        ),
        headers=member_headers,
    )
    assert adjacent.status_code == 201


def test_cancelled_reservation_releases_inventory(
    client, seed, member_headers
):
    payload = reservation_payload(
        seed.venue,
        seed.small,
        days_from=7,
        hour=10,
        hours=2,
    )
    first = client.post("/api/reservations", json=payload, headers=member_headers)
    assert first.status_code == 201
    assert (
        client.post("/api/reservations", json=payload, headers=member_headers).status_code
        == 400
    )

    assert (
        client.post(
            f"/api/reservations/{first.json()['id']}/cancel",
            headers=member_headers,
        ).status_code
        == 200
    )
    retry = client.post("/api/reservations", json=payload, headers=member_headers)
    assert retry.status_code == 201


def test_my_reservations_returns_only_own_records(
    client, seed, member_headers, stranger_headers
):
    mine = client.post(
        "/api/reservations",
        json=reservation_payload(
            seed.venue,
            seed.boardroom,
            days_from=7,
        ),
        headers=member_headers,
    ).json()
    client.post(
        "/api/reservations",
        json=reservation_payload(
            seed.venue,
            seed.boardroom,
            days_from=20,
        ),
        headers=stranger_headers,
    )

    response = client.get("/api/reservations/my", headers=member_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [mine["id"]]


def test_availability_reports_remaining_and_available(
    client, seed, member_headers
):
    client.post(
        "/api/reservations",
        json=reservation_payload(
            seed.venue,
            seed.small,
            days_from=7,
            hour=10,
            hours=2,
        ),
        headers=member_headers,
    )

    response = client.get(
        f"/api/venues/{seed.venue.id}/availability",
        params={"start_at": _iso_days(7, 10), "end_at": _iso_days(7, 12)},
        headers=member_headers,
    )
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["meeting_rooms"]}

    small = items[seed.small.id]
    assert small["quantity"] == 1
    assert small["remaining"] == 0
    assert small["available"] is False

    boardroom = items[seed.boardroom.id]
    assert boardroom["remaining"] == 3
    assert boardroom["available"] is True

    maintenance = items[seed.maintenance.id]
    assert maintenance["remaining"] == 2
    assert maintenance["available"] is False


def test_availability_rejects_reversed_time(client, seed, member_headers):
    response = client.get(
        f"/api/venues/{seed.venue.id}/availability",
        params={"start_at": _iso_days(9), "end_at": _iso_days(7)},
        headers=member_headers,
    )
    assert response.status_code == 400
    assert "结束时间必须晚于开始时间" in response.json()["detail"]


def test_availability_returns_404_for_unknown_venue(
    client, seed, member_headers
):
    response = client.get(
        "/api/venues/9999/availability",
        params={"start_at": _iso_days(7), "end_at": _iso_days(7, 12)},
        headers=member_headers,
    )
    assert response.status_code == 404


def test_create_reservation_rejects_outside_opening_hours(
    client, seed, member_headers
):
    payload = reservation_payload(
        seed.venue,
        seed.boardroom,
        days_from=7,
        hour=19,
        hours=2,
    )
    response = client.post("/api/reservations", json=payload, headers=member_headers)
    assert response.status_code == 400
    assert "08:30-20:00" in response.json()["detail"]
