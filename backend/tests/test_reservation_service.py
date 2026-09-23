"""预约业务规则：晚数、库存区间占用、剩余会议室余量与价格计算（service 层）。"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.schemas.reservation import ReservationIn
from app.services.reservation_service import (
    build_reservation,
    hours_between,
    occupied_rooms,
    remaining_rooms,
    validate_reservation,
)
from helpers import seed_reservation


def _in(days: int) -> date:
    return date.today() + timedelta(days=days)


def _payload(
    venue, meeting_room, *, check_in: date, check_out: date, rooms: int = 1, attendees: int = 2, **extra
):
    return ReservationIn(
        venue_id=venue.id,
        meeting_room_id=meeting_room.id,
        start_at=check_in,
        end_at=check_out,
        rooms=rooms,
        attendees=attendees,
        **extra,
    )


# ---------- 晚数 ----------


def test_hours_between_counts_calendar_days():
    assert hours_between(date(2026, 9, 21), date(2026, 9, 24)) == 3
    assert hours_between(date(2026, 9, 21), date(2026, 9, 22)) == 1


def test_hours_between_crosses_month_boundary():
    assert hours_between(date(2026, 9, 30), date(2026, 10, 2)) == 2


# ---------- 库存区间占用 ----------


def test_occupied_rooms_is_zero_without_reservation(db, seed):
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 0


@pytest.mark.parametrize(
    "existing_in, existing_out, query_in, query_out",
    [
        (7, 9, 7, 9),  # 完全重合
        (7, 9, 8, 10),  # 右侧部分重合
        (7, 9, 6, 8),  # 左侧部分重合
        (7, 12, 8, 9),  # 查询区间被包含
        (8, 9, 7, 12),  # 查询区间包含已有
        (7, 9, 8, 9),  # 单晚落在区间内
    ],
)
def test_occupied_rooms_counts_overlapping_ranges(db, seed, existing_in, existing_out, query_in, query_out):
    seed_reservation(
        db,
        user=seed.member,
        venue=seed.venue,
        meeting_room=seed.king,
        rooms=1,
        days_from=existing_in,
        hours=existing_out - existing_in,
    )
    assert occupied_rooms(db, seed.king.id, _in(query_in), _in(query_out)) == 1


def test_occupied_rooms_ignores_adjacent_range(db, seed):
    """[使用开始, 使用结束) 左闭右开：上一单使用结束当天使用开始不算占用。"""
    seed_reservation(db, user=seed.member, venue=seed.venue, meeting_room=seed.king, days_from=7, hours=2)
    assert occupied_rooms(db, seed.king.id, _in(9), _in(11)) == 0
    assert occupied_rooms(db, seed.king.id, _in(5), _in(7)) == 0


@pytest.mark.parametrize("status", ["rejected", "canceled"])
def test_occupied_rooms_ignores_inactive_status(db, seed, status):
    seed_reservation(
        db, user=seed.member, venue=seed.venue, meeting_room=seed.king, rooms=2, status=status, days_from=7, hours=2
    )
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 0


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_occupied_rooms_counts_active_status(db, seed, status):
    seed_reservation(
        db, user=seed.member, venue=seed.venue, meeting_room=seed.king, rooms=2, status=status, days_from=7, hours=2
    )
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 2


def test_occupied_rooms_sums_multiple_reservations(db, seed):
    seed_reservation(db, user=seed.member, venue=seed.venue, meeting_room=seed.king, rooms=1, days_from=7, hours=2)
    seed_reservation(db, user=seed.stranger, venue=seed.venue, meeting_room=seed.king, rooms=2, days_from=8, hours=2)
    assert occupied_rooms(db, seed.king.id, _in(8), _in(9)) == 3


def test_occupied_rooms_excludes_own_reservation(db, seed):
    reservation = seed_reservation(
        db, user=seed.member, venue=seed.venue, meeting_room=seed.king, rooms=2, days_from=7, hours=2
    )
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 2
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9), exclude_id=reservation.id) == 0


def test_occupied_rooms_only_counts_target_meeting_room(db, seed):
    seed_reservation(db, user=seed.member, venue=seed.venue, meeting_room=seed.twin, rooms=1, days_from=7, hours=2)
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 0


# ---------- 剩余会议室余量 ----------


def test_remaining_rooms_equals_quantity_minus_occupied(db, seed):
    seed_reservation(db, user=seed.member, venue=seed.venue, meeting_room=seed.king, rooms=2, days_from=7, hours=2)
    assert seed.king.quantity == 3
    assert remaining_rooms(db, seed.king, _in(7), _in(9)) == 1


def test_remaining_rooms_never_negative(db, seed):
    """历史脏数据导致占用超过会议室余量时，剩余会议室余量兜底为 0。"""
    seed_reservation(db, user=seed.member, venue=seed.venue, meeting_room=seed.twin, rooms=5, days_from=7, hours=2)
    assert remaining_rooms(db, seed.twin, _in(7), _in(9)) == 0


# ---------- 下单校验 ----------


def test_validate_rejects_check_in_before_today(db, seed):
    payload = _payload(seed.venue, seed.king, check_in=_in(-1), check_out=_in(1))
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert error.value.status_code == 400
    assert "使用开始日期不能早于今天" in error.value.detail


def test_validate_rejects_rooms_over_quantity(db, seed):
    payload = _payload(seed.venue, seed.king, check_in=_in(7), check_out=_in(9), rooms=20, attendees=2)
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "会议室余量只有" in error.value.detail


def test_validate_rejects_attendees_over_capacity(db, seed):
    payload = _payload(seed.venue, seed.king, check_in=_in(7), check_out=_in(9), rooms=2, attendees=5)
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "使用开始人数超过上限" in error.value.detail


def test_validate_allows_attendees_up_to_capacity_times_rooms(db, seed):
    payload = _payload(seed.venue, seed.king, check_in=_in(7), check_out=_in(9), rooms=2, attendees=4)
    venue, meeting_room = validate_reservation(db, seed.member, payload)
    assert venue.id == seed.venue.id
    assert meeting_room.id == seed.king.id


def test_validate_rejects_closed_venue(db, seed):
    payload = _payload(seed.closed_venue, seed.closed_room, check_in=_in(7), check_out=_in(9))
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert error.value.status_code == 400
    assert "暂停营业" in error.value.detail


def test_validate_rejects_unopened_meeting_room(db, seed):
    payload = _payload(seed.venue, seed.maintenance, check_in=_in(7), check_out=_in(9))
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "暂不可预约" in error.value.detail


def test_validate_rejects_meeting_room_from_other_venue(db, seed):
    payload = _payload(seed.venue, seed.closed_room, check_in=_in(7), check_out=_in(9))
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "不属于所选会议空间" in error.value.detail


def test_validate_rejects_missing_venue(db, seed):
    payload = ReservationIn(
        venue_id=9999,
        meeting_room_id=seed.king.id,
        start_at=_in(7),
        end_at=_in(9),
        rooms=1,
        attendees=2,
    )
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert error.value.status_code == 404


def test_validate_rejects_oversell_with_remaining_in_message(db, seed):
    """双床房只有 1 间：已被占用后再订 1 间必须被拒，并提示剩余数量。"""
    seed_reservation(db, user=seed.member, venue=seed.venue, meeting_room=seed.twin, rooms=1, days_from=7, hours=2)
    payload = _payload(seed.venue, seed.twin, check_in=_in(7), check_out=_in(9))
    with pytest.raises(HTTPException) as error:
        validate_reservation(db, seed.member, payload)
    assert "仅剩 0 间可订" in error.value.detail


# ---------- 价格与落库前的构造 ----------


def test_build_reservation_calculates_total_amount(db, seed):
    payload = _payload(seed.venue, seed.king, check_in=_in(7), check_out=_in(10), rooms=2, attendees=4)
    reservation = build_reservation(db, seed.member, payload)
    assert reservation.hours == 3
    assert reservation.total_amount == Decimal("458") * 3 * 2
    assert float(reservation.total_amount) == 2748.0


def test_build_reservation_sets_pending_status_and_owner(db, seed):
    payload = _payload(seed.venue, seed.king, check_in=_in(7), check_out=_in(8))
    reservation = build_reservation(db, seed.member, payload)
    assert reservation.status == "pending"
    assert reservation.user_id == seed.member.id
    assert reservation.remark == ""


def test_build_reservation_falls_back_to_user_phone(db, seed):
    seed.member.phone = "13800000000"
    payload = _payload(seed.venue, seed.king, check_in=_in(7), check_out=_in(8))
    reservation = build_reservation(db, seed.member, payload)
    assert reservation.contact_phone == "13800000000"


def test_build_reservation_keeps_explicit_phone(db, seed):
    seed.member.phone = "13800000000"
    payload = _payload(seed.venue, seed.king, check_in=_in(7), check_out=_in(8), contact_phone="13911112222")
    reservation = build_reservation(db, seed.member, payload)
    assert reservation.contact_phone == "13911112222"
