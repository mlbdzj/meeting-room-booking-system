"""自然语言预约：解析口语需求 -> 生成预约草稿 -> 用户确认后下单。"""

import re
from datetime import date as date_type
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools import detect_date, match_venue
from app.models import Reservation, Venue, MeetingRoom, User
from app.schemas.reservation import ReservationIn
from app.services.reservation_service import create_reservation, hours_between, validate_reservation

DEFAULT_NIGHTS = 1

DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_NUM = r"\d{1,3}|[零一二两三四五六七八九十]{1,3}"

NIGHTS_PATTERN = re.compile(rf"(?<!入)(?:住|共|连住)?\s*(?P<num>{CN_NUM})\s*(?:晚|夜)")
ROOMS_PATTERN = re.compile(rf"(?P<num>{CN_NUM})\s*(?:间|间房|间会议室)")
GUESTS_PATTERN = re.compile(rf"(?P<num>{CN_NUM})\s*(?:个|位|名)?\s*(?:人|客人|成人|住客)")
CHECKOUT_PATTERN = re.compile(rf"(?P<num>{CN_NUM})\s*[日号]?\s*(?:使用结束|离店)")

FILLER_WORDS = (
    "帮我",
    "帮忙",
    "我想",
    "我要",
    "要",
    "请",
    "预约",
    "预定",
    "订",
    "的房间",
    "房间",
    "使用开始",
    "住",
    "晚",
    "天",
    "一共",
    "共",
    "个",
    "位",
    "名",
    "人",
    "间",
    "的",
    "去",
    "在",
    "和",
    "一起",
    "需要",
)


def cn_to_int(text: str) -> int | None:
    value = (text or "").strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        tens = DIGITS.get(left, 1) if left else 1
        ones = DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    total = 0
    for char in value:
        if char not in DIGITS:
            return None
        total = total * 10 + DIGITS[char]
    return total


def _match_number(pattern: re.Pattern, text: str) -> int | None:
    match = pattern.search(text or "")
    if not match:
        return None
    return cn_to_int(match.group("num"))


def parse_hours(text: str) -> int | None:
    return _match_number(NIGHTS_PATTERN, text)


def parse_rooms(text: str) -> int | None:
    return _match_number(ROOMS_PATTERN, text)


def parse_attendees(text: str) -> int | None:
    return _match_number(GUESTS_PATTERN, text)


def match_meeting_room(db: Session, venue: Venue | None, text: str) -> MeetingRoom | None:
    if venue is None:
        return None
    normalized = (text or "").replace(" ", "")
    for meeting_room in db.scalars(select(MeetingRoom).where(MeetingRoom.venue_id == venue.id)).all():
        for candidate in {meeting_room.name, meeting_room.layout}:
            if candidate and candidate.replace(" ", "") in normalized:
                return meeting_room
    return None


def extract_equipment_request(text: str, venue: Venue | None, meeting_room: MeetingRoom | None) -> str:
    remaining = text or ""
    for item in (venue.name if venue else "", meeting_room.name if meeting_room else "", meeting_room.layout if meeting_room else ""):
        if item:
            remaining = remaining.replace(item, "").replace(item.replace(" ", ""), "")
    for word in ("今天", "明天", "后天", "下周一", "下周二", "下周三", "下周四", "下周五", "下周六", "下周日"):
        remaining = remaining.replace(word, "")
    remaining = re.sub(r"((下个?)+|本|这)?(周|星期)[一二三四五六日天]", "", remaining)
    remaining = remaining.replace("使用开始", "").replace("使用结束", "").replace("离店", "")
    remaining = NIGHTS_PATTERN.sub("", remaining)
    remaining = ROOMS_PATTERN.sub("", remaining)
    remaining = GUESTS_PATTERN.sub("", remaining)
    remaining = re.sub(r"\d{4}\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}\s*[日号]?", "", remaining)
    remaining = re.sub(r"\d{1,2}\s*[-/月]\s*\d{1,2}\s*[日号]?", "", remaining)
    remaining = re.sub(r"\d{1,2}\s*[日号]", "", remaining)
    # 先删长词再删短词，避免「需要安静楼层」被切成「需安静楼层」
    for word in sorted(FILLER_WORDS, key=len, reverse=True):
        remaining = remaining.replace(word, "")
    remaining = re.sub(r"[，。,.、！!？?；;:：\s]+", "", remaining)
    return remaining[:60] if len(remaining) >= 2 else ""


def parse_reservation_text(db: Session, text: str) -> dict:
    venue = match_venue(db, text)
    meeting_room = match_meeting_room(db, venue, text)
    check_in = detect_date(text)
    hours = parse_hours(text)

    check_out = None
    match = CHECKOUT_PATTERN.search(text)
    if match and check_in is not None:
        day = cn_to_int(match.group("num"))
        if day and 1 <= day <= 31:
            candidate = date_type(check_in.year, check_in.month, day)
            if candidate <= check_in:
                candidate = candidate + timedelta(days=32)
                candidate = date_type(candidate.year, candidate.month, day)
            check_out = candidate

    single_night_assumed = False
    if check_out is None and check_in is not None:
        if hours:
            check_out = check_in + timedelta(days=hours)
        else:
            check_out = check_in + timedelta(days=DEFAULT_NIGHTS)
            single_night_assumed = True

    return {
        "venue": venue,
        "venue_name": venue.name if venue else "",
        "meeting_room": meeting_room,
        "meeting_room_name": meeting_room.name if meeting_room else "",
        "start_at": check_in,
        "end_at": check_out,
        "hours": hours_between(check_in, check_out) if check_in and check_out else hours,
        "rooms": parse_rooms(text),
        "attendees": parse_attendees(text),
        "equipment_request": extract_equipment_request(text, venue, meeting_room),
        "assumed_single_night": single_night_assumed,
    }


def build_draft(
    db: Session,
    user: User,
    *,
    venue: Venue | None,
    venue_name: str = "",
    meeting_room: MeetingRoom | None,
    start_at: date_type | None,
    end_at: date_type | None,
    rooms: int | None,
    attendees: int | None,
    equipment_request: str = "",
    note: str = "",
) -> dict:
    """生成预约草稿：包含解析结果、校验问题与摘要，不写数据库。"""
    problems: list[str] = []
    rooms = rooms or 1

    if venue is None:
        problems.append(f"没有找到名为「{venue_name}」的会议空间，请确认会议空间名称" if venue_name else "还需要确认预约哪家会议空间")
    if meeting_room is None:
        problems.append("还需要确认会议室类型（例如大床房、双床房）")
    if start_at is None:
        problems.append("还需要确认使用开始日期")
    if end_at is None:
        problems.append("还需要确认使用结束日期或使用开始晚数")
    if attendees is None:
        problems.append("还需要确认使用开始人数")
    if start_at and end_at and end_at <= start_at:
        problems.append("使用结束日期必须晚于使用开始日期")

    hours = hours_between(start_at, end_at) if start_at and end_at else None
    price = float(meeting_room.price or 0) if meeting_room else 0
    total_amount = round(price * (hours or 0) * rooms, 2)

    if not problems and venue and meeting_room and start_at and end_at:
        payload = ReservationIn(
            venue_id=venue.id,
            meeting_room_id=meeting_room.id,
            start_at=start_at,
            end_at=end_at,
            rooms=rooms,
            attendees=attendees or 1,
            equipment_request=equipment_request or "",
        )
        try:
            validate_reservation(db, user, payload)
        except HTTPException as error:
            problems.append(str(error.detail))

    draft = {
        "type": "reservation_draft",
        "status": "invalid" if problems else "pending",
        "problems": problems,
        "note": note,
        "payload": {
            "venue_id": venue.id if venue else None,
            "venue_name": venue.name if venue else (venue_name or ""),
            "meeting_room_id": meeting_room.id if meeting_room else None,
            "meeting_room_name": meeting_room.name if meeting_room else "",
            "start_at": start_at.isoformat() if start_at else "",
            "end_at": end_at.isoformat() if end_at else "",
            "hours": hours,
            "rooms": rooms,
            "attendees": attendees,
            "price": price,
            "total_amount": total_amount,
            "equipment_request": equipment_request or "",
        },
        "summary": "",
        "reservation_id": None,
    }
    draft["summary"] = summarize_draft(draft)
    return draft


def summarize_draft(draft: dict) -> str:
    payload = draft["payload"]
    if draft["problems"]:
        return "还差这些信息或需要调整：" + "；".join(draft["problems"])

    def weekday(value: str) -> str:
        try:
            target = date_type.fromisoformat(value)
        except ValueError:
            return ""
        return "（周" + "一二三四五六日"[target.weekday()] + "）"

    return (
        f"{payload['venue_name']}｜{payload['meeting_room_name']}｜"
        f"{payload['start_at']}{weekday(payload['start_at'])} 使用开始，"
        f"{payload['end_at']} 使用结束，共 {payload['hours']} 晚｜"
        f"{payload['rooms']} 间 / {payload['attendees']} 人｜"
        f"总价 ¥{payload['total_amount']:.0f}"
        + (f"｜特殊要求：{payload['equipment_request']}" if payload["equipment_request"] else "")
    )


def prepare_from_text(db: Session, user: User, text: str) -> dict:
    parsed = parse_reservation_text(db, text)
    note = ""
    if parsed.get("assumed_single_night"):
        note = "没有识别到使用开始晚数，暂按 1 晚计算，如需调整请重新说明。"
    return build_draft(
        db,
        user,
        venue=parsed["venue"],
        venue_name=parsed["venue_name"],
        meeting_room=parsed["meeting_room"],
        start_at=parsed["start_at"],
        end_at=parsed["end_at"],
        rooms=parsed["rooms"],
        attendees=parsed["attendees"],
        equipment_request=parsed["equipment_request"],
        note=note,
    )


def prepare_from_arguments(db: Session, user: User, arguments: dict) -> dict:
    """大模型工具入口：合并结构化参数与原始描述后生成草稿。"""
    raw_text = str(arguments.get("raw_text") or arguments.get("text") or "").strip()
    parsed = parse_reservation_text(db, raw_text) if raw_text else {}

    venue = match_venue(db, str(arguments.get("venue_name") or "")) or parsed.get("venue")
    meeting_room = match_meeting_room(db, venue, str(arguments.get("meeting_room_name") or "")) or parsed.get("meeting_room")

    check_in = detect_date(str(arguments.get("check_in") or "")) or parsed.get("start_at")
    check_out = detect_date(str(arguments.get("check_out") or "")) or parsed.get("end_at")

    hours = arguments.get("hours")
    try:
        hours = int(hours) if hours is not None else parsed.get("hours")
    except (TypeError, ValueError):
        hours = parsed.get("hours")
    if check_in and not check_out and hours:
        check_out = check_in + timedelta(days=hours)

    def _int(value, fallback):
        try:
            return int(value) if value is not None else fallback
        except (TypeError, ValueError):
            return fallback

    rooms = _int(arguments.get("rooms"), parsed.get("rooms"))
    attendees = _int(arguments.get("attendees"), parsed.get("attendees"))
    equipment_request = str(arguments.get("equipment_request") or "").strip() or parsed.get("equipment_request") or ""

    note = ""
    if parsed.get("assumed_single_night") and not check_out:
        note = "没有识别到使用开始晚数，暂按 1 晚计算，如需调整请重新说明。"

    return build_draft(
        db,
        user,
        venue=venue,
        venue_name=str(arguments.get("venue_name") or ""),
        meeting_room=meeting_room,
        start_at=check_in,
        end_at=check_out,
        rooms=rooms,
        attendees=attendees,
        equipment_request=equipment_request,
        note=note,
    )


def confirm_draft(db: Session, user: User, draft: dict) -> Reservation:
    """用户确认后真正创建预约，仍然走完整校验（含会议室余量库存）。"""
    payload = draft.get("payload") or {}
    if not payload.get("venue_id") or not payload.get("meeting_room_id"):
        raise HTTPException(status_code=400, detail="预约信息不完整，请重新发起预约")

    reservation_payload = ReservationIn(
        venue_id=payload["venue_id"],
        meeting_room_id=payload["meeting_room_id"],
        start_at=date_type.fromisoformat(payload["start_at"]),
        end_at=date_type.fromisoformat(payload["end_at"]),
        rooms=int(payload.get("rooms") or 1),
        attendees=int(payload.get("attendees") or 1),
        equipment_request=(payload.get("equipment_request") or "")[:200],
    )
    return create_reservation(db, user, reservation_payload)
