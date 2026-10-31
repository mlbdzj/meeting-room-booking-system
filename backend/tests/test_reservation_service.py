"""预约业务规则：时长、时段重叠、余量、容量与价格计算。"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.schemas.reservation import ReservationIn
from app.services.reservation_service import (
    build_reservation,
    duration_hours,
    occupied_rooms,
    remaining_rooms,
    validate_reservation,
)
from helpers import seed_reservation, slot


def _at(days: int, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(
        date.today() + timedelta(days=days),
        time(hour, minute),
    )


def _payload(
    venue,
    meeting_room,
    *,
    start_at: datetime,
    end_at: datetime,
    rooms: int = 1,
    attendees: int = 2,
    **extra,
):
    return ReservationIn(
        venue_id=venue.id,
        meeting_room_id=meeting_room.id,
        start_at=start_at,
        end_at=end_at,
        rooms=rooms,
        attendees=attendees,
        **extra,
    )


def test_duration_hours_supports_half_hours():
    start_at = datetime(2026, 11, 6, 10, 0)
    assert duration_hours(start_at, start_at + timedelta(hours=2)) == 2.0
    assert duration_hours(start_at, start_at + timedelta(minutes=90)) == 1.5


def test_occupied_rooms_is_zero_without_reservation(db, seed):
    start_at, end_at = slot(days_from=7)
    assert occupied_rooms(db, seed.boardroom.id, start_at, end_at) == 0


@pytest.mark.parametrize(
    "existing_offset, existing_duration, query_offset, query_duration",
    [
        (0, 2, 0, 2),
        (0, 2, 1, 2),
        (0, 2, -1, 2),
        (0, 5, 1, 1),
        (1, 1, 0, 5),
        (0, 2, 1, 1),
    ],
)
def test_occupied_rooms_counts_overlapping_windows(
    db,
    seed,
    existing_offset,
    existing_duration,
    query_offset,
    query_duration,
):
    baseline = _at(7, 10)
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.boardroom,
        rooms=1,
        days_from=7,
        hour=10,
        hours=existing_duration,
    )
    query_start = baseline + timedelta(hours=query_offset)
    query_end = query_start + timedelta(hours=query_duration)
    existing_start = baseline + timedelta(hours=existing_offset)
    existing_end = existing_start + timedelta(hours=existing_duration)
    assert existing_start <= query_end and existing_end >= query_start
    assert occupied_rooms(
        db,
        seed.boardroom.id,
        query_start,
        query_end,
    ) == 1


def test_occupied_rooms_ignores_adjacent_window(db, seed):
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.boardroom,
        days_from=7,
        hours=2,
    )
    assert occupied_rooms(db, seed.boardroom.id, _at(7, 12), _at(7, 14)) == 0
    assert occupied_rooms(db, seed.boardroom.id, _at(7, 8), _at(7, 10)) == 0


@pytest.mark.parametrize("status", ["rejected", "canceled"])
def test_occupied_rooms_ignores_inactive_status(db, seed, status):
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.boardroom,
        rooms=2,
        status=status,
    )
    start_at, end_at = slot(days_from=7)
    assert occupied_rooms(db, seed.boardroom.id, start_at, end_at) == 0


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_occupied_rooms_counts_active_status(db, seed, status):
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.boardroom,
        rooms=2,
        status=status,
    )
    start_at, end_at = slot(days_from=7)
    assert occupied_rooms(db, seed.boardroom.id, start_at, end_at) == 2


def test_occupied_rooms_sums_multiple_reservations(db, seed):
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.boardroom,
        rooms=1,
        days_from=7,
    )
    seed_reservation(
        db,
        user=seed.stranger,
        venue=seed.venue,
        meeting_room=seed.boardroom,
        rooms=2,
        days_from=7,
        hour=11,
    )
    assert occupied_rooms(
        db, seed.boardroom.id, _at(7, 11), _at(7, 12)
    ) == 3


def test_occupied_rooms_excludes_own_reservation(db, seed):
    reservation = seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.boardroom,
        rooms=2,
    )
    start_at, end_at = slot(days_from=7)
    assert occupied_rooms(db, seed.boardroom.id, start_at, end_at) == 2
    assert (
        occupied_rooms(
            db,
            seed.boardroom.id,
            start_at,
            end_at,
            exclude_id=reservation.id,
        )
        == 0
    )


def test_occupied_rooms_only_counts_target_room(db, seed):
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.small,
    )
    start_at, end_at = slot(days_from=7)
    assert occupied_rooms(db, seed.boardroom.id, start_at, end_at) == 0


def test_remaining_rooms_equals_quantity_minus_occupied(db, seed):
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.boardroom,
        rooms=2,
    )
    start_at, end_at = slot(days_from=7)
    assert seed.boardroom.quantity == 3
    assert remaining_rooms(db, seed.boardroom, start_at, end_at) == 1


def test_remaining_rooms_never_negative(db, seed):
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.small,
        rooms=5,
    )
    start_at, end_at = slot(days_from=7)
    assert remaining_rooms(db, seed.small, start_at, end_at) == 0


def test_validate_rejects_past_start(db, seed):
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=_at(-1, 10),
        end_at=_at(-1, 12),
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "开始时间不能早于当前时间" in error.value.detail


def test_validate_accepts_minute_precision(db, seed):
    start_at, _ = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=start_at.replace(minute=17),
        end_at=start_at.replace(minute=47),
    )
    venue, meeting_room = validate_reservation(db, seed.member, payload)
    assert venue.id == seed.venue.id
    assert meeting_room.id == seed.boardroom.id


def test_validate_rejects_rooms_over_quantity(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=start_at,
        end_at=end_at,
        rooms=20,
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "仅有 3 间" in error.value.detail


def test_validate_rejects_attendees_over_capacity(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=start_at,
        end_at=end_at,
        rooms=2,
        attendees=25,
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "参会人数超过上限" in error.value.detail


def test_validate_allows_attendees_up_to_capacity_times_rooms(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=start_at,
        end_at=end_at,
        rooms=2,
        attendees=20,
    )
    venue, meeting_room = validate_reservation(db, seed.member, payload)
    assert venue.id == seed.venue.id
    assert meeting_room.id == seed.boardroom.id


def test_validate_rejects_closed_venue(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.closed_venue,
        seed.closed_room,
        start_at=start_at,
        end_at=end_at,
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "暂未开放预约" in error.value.detail


def test_validate_rejects_unopened_meeting_room(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.maintenance,
        start_at=start_at,
        end_at=end_at,
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "暂不可预约" in error.value.detail


def test_validate_rejects_meeting_room_from_other_venue(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.closed_room,
        start_at=start_at,
        end_at=end_at,
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "不属于所选空间" in error.value.detail


def test_validate_rejects_outside_opening_hours(db, seed):
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=_at(7, 19),
        end_at=_at(7, 21),
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "开放时段 08:30-20:00" in error.value.detail


def test_validate_rejects_missing_venue(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = ReservationIn(
        venue_id=9999,
        meeting_room_id=seed.boardroom.id,
        start_at=start_at,
        end_at=end_at,
        rooms=1,
        attendees=2,
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert error.value.status_code == 404


def test_validate_rejects_oversell_with_remaining_in_message(db, seed):
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.small,
        rooms=1,
    )
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.small,
        start_at=start_at,
        end_at=end_at,
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "仅剩 0 间可预约" in error.value.detail


def test_build_reservation_calculates_total_amount(db, seed):
    start_at, end_at = slot(days_from=7, hours=3)
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=start_at,
        end_at=end_at,
        rooms=2,
        attendees=20,
    )
    reservation = build_reservation(db, seed.member, payload)
    assert float(reservation.hours) == 3.0
    assert reservation.total_amount == Decimal("120") * 3 * 2
    assert float(reservation.total_amount) == 720.0


def test_build_reservation_sets_pending_status_and_owner(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=start_at,
        end_at=end_at,
    )
    reservation = build_reservation(db, seed.member, payload)
    assert reservation.status == "pending"
    assert reservation.user_id == seed.member.id
    assert reservation.remark == ""


def test_build_reservation_falls_back_to_user_phone(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=start_at,
        end_at=end_at,
    )
    reservation = build_reservation(db, seed.member, payload)
    assert reservation.contact_phone == "13800000000"


def test_build_reservation_keeps_explicit_phone(db, seed):
    start_at, end_at = slot(days_from=7)
    payload = _payload(
        seed.venue,
        seed.boardroom,
        start_at=start_at,
        end_at=end_at,
        contact_phone="13911112222",
    )
    reservation = build_reservation(db, seed.member, payload)
    assert reservation.contact_phone == "13911112222"
