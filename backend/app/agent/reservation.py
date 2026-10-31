"""自然语言会议室预约：解析口语需求 -> 生成草稿 -> 用户确认后写库。"""

import re
from datetime import date as date_type
from datetime import datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools import (
    cn_to_int,
    detect_date,
    detect_datetime,
    match_meeting_room,
    match_venue,
    meeting_room_aliases,
)
from app.models import MeetingRoom, Reservation, User, Venue
from app.schemas.reservation import ReservationIn
from app.services.reservation_service import (
    create_reservation,
    duration_hours,
    validate_reservation,
)

DEFAULT_HOURS = 2
CN_NUM = r"\d{1,3}(?:\.\d{1,2})?|[零一二两三四五六七八九十]{1,3}"

HOURS_PATTERN = re.compile(
    rf"(?P<num>{CN_NUM})\s*(?:个)?\s*(?:小时|钟头)"
)
MINUTES_PATTERN = re.compile(rf"(?P<num>{CN_NUM})\s*分钟")
ROOMS_PATTERN = re.compile(
    rf"(?P<num>{CN_NUM})\s*(?:间|间会议室|个会议室)"
)
ATTENDEES_PATTERN = re.compile(
    rf"(?P<num>{CN_NUM})\s*(?:个|位|名)?\s*(?:人|参会人|参会人员|客人)"
)

TIME_TOKEN = (
    r"(?:(上午|早上|中午|下午|晚上)\s*)?"
    r"(\d{1,2})(?::(\d{2})|点(?:半|(\d{1,2})分?)?)"
)
TIME_RANGE_PATTERN = re.compile(
    rf"{TIME_TOKEN}\s*(?:到|至|—|-)\s*{TIME_TOKEN}"
)

FILLER_WORDS = (
    "帮我",
    "帮忙",
    "我想",
    "我要",
    "麻烦",
    "请",
    "预约",
    "预定",
    "订",
    "使用",
    "举办",
    "开会",
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
    "从",
)


def _number(text: str) -> int | None:
    value = (text or "").strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return cn_to_int(value)


def _time_from_parts(
    period: str | None, hour_text: str, minute_text: str | None, half: str | None
) -> time | None:
    hour = int(hour_text)
    minute = 30 if half else int(minute_text or 0)
    if period in {"下午", "晚上"} and hour < 12:
        hour += 12
    if period == "中午" and hour < 11:
        hour += 12
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def extract_time_range(text: str) -> tuple[time | None, time | None]:
    match = TIME_RANGE_PATTERN.search(text or "")
    if not match:
        return None, None
    start = _time_from_parts(
        match.group(1), match.group(2), match.group(3), match.group(4)
    )
    end = _time_from_parts(
        match.group(5), match.group(6), match.group(7), match.group(8)
    )
    if start and end and end <= start and not match.group(5):
        end = time((end.hour + 12) % 24, end.minute)
    return start, end


def parse_hours(text: str) -> float | None:
    if re.search(r"(?:一|1)\s*个?\s*半小时", text or ""):
        return 1.5
    if "半小时" in (text or ""):
        return 0.5
    minute_match = MINUTES_PATTERN.search(text or "")
    if minute_match:
        minutes = _number(minute_match.group("num"))
        if minutes:
            return round(minutes / 60, 2)
    if "半天" in (text or ""):
        return 4
    if "一天" in (text or "") or "全天" in (text or ""):
        return 8
    match = HOURS_PATTERN.search(text or "")
    if not match:
        return None
    value = match.group("num")
    try:
        return float(value)
    except ValueError:
        number = cn_to_int(value)
        return float(number) if number is not None else None


def parse_rooms(text: str) -> int | None:
    match = ROOMS_PATTERN.search(text or "")
    return _number(match.group("num")) if match else None


def parse_attendees(text: str) -> int | None:
    match = ATTENDEES_PATTERN.search(text or "")
    return _number(match.group("num")) if match else None


def extract_equipment_request(
    text: str,
    venue: Venue | None,
    meeting_room: MeetingRoom | None,
) -> str:
    remaining = text or ""
    for item in (
        venue.name if venue else "",
        meeting_room.name if meeting_room else "",
        meeting_room.layout if meeting_room else "",
    ):
        if item:
            remaining = remaining.replace(item, "").replace(item.replace(" ", ""), "")
    for word in (
        "今天",
        "明天",
        "后天",
        "下周一",
        "下周二",
        "下周三",
        "下周四",
        "下周五",
        "下周六",
        "下周日",
    ):
        remaining = remaining.replace(word, "")
    remaining = re.sub(r"((下个?)+|本|这)?(周|星期)[一二三四五六日天]", "", remaining)
    remaining = TIME_RANGE_PATTERN.sub("", remaining)
    remaining = HOURS_PATTERN.sub("", remaining)
    remaining = MINUTES_PATTERN.sub("", remaining)
    remaining = ROOMS_PATTERN.sub("", remaining)
    remaining = ATTENDEES_PATTERN.sub("", remaining)
    remaining = re.sub(
        r"\d{4}\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}\s*[日号]?", "", remaining
    )
    remaining = re.sub(r"\d{1,2}\s*[-/月]\s*\d{1,2}\s*[日号]?", "", remaining)
    for word in sorted(FILLER_WORDS, key=len, reverse=True):
        remaining = remaining.replace(word, "")
    remaining = re.sub(r"[，。,.、！!？?；;:：\s]+", "", remaining)
    return remaining[:100] if len(remaining) >= 2 else ""


def parse_reservation_text(db: Session, text: str) -> dict:
    venue = match_venue(db, text)
    meeting_room = match_meeting_room(db, venue, text)
    if venue is None:
        normalized = (text or "").replace(" ", "")
        best_match = None
        best_length = 0
        for candidate in db.scalars(select(MeetingRoom)).all():
            for alias in meeting_room_aliases(candidate):
                if alias in normalized and len(alias) > best_length:
                    best_match = candidate
                    best_length = len(alias)
        if best_match is not None:
            meeting_room = best_match
            venue = db.get(Venue, best_match.venue_id)
    target_date = detect_date(text)
    start_time, end_time = extract_time_range(text)
    hours = parse_hours(text)
    assumed_default_time = False

    if target_date and start_time is None:
        start_time = time(9, 0)
        assumed_default_time = True
    if target_date and start_time and end_time is None:
        end_time = (
            datetime.combine(target_date, start_time) + timedelta(hours=hours or DEFAULT_HOURS)
        ).time()
        if end_time <= start_time:
            end_time = time(23, 59)

    start_at = (
        datetime.combine(target_date, start_time)
        if target_date and start_time
        else None
    )
    end_at = (
        datetime.combine(target_date, end_time)
        if target_date and end_time
        else None
    )
    if start_at and end_at and end_at <= start_at:
        end_at += timedelta(days=1)

    return {
        "venue": venue,
        "venue_name": venue.name if venue else "",
        "meeting_room": meeting_room,
        "meeting_room_name": meeting_room.name if meeting_room else "",
        "start_at": start_at,
        "end_at": end_at,
        "hours": (
            duration_hours(start_at, end_at)
            if start_at and end_at
            else hours
        ),
        "rooms": parse_rooms(text),
        "attendees": parse_attendees(text),
        "equipment_request": extract_equipment_request(text, venue, meeting_room),
        "assumed_default_time": assumed_default_time,
    }


def build_draft(
    db: Session,
    user: User,
    *,
    venue: Venue | None,
    venue_name: str = "",
    meeting_room: MeetingRoom | None,
    start_at: datetime | None,
    end_at: datetime | None,
    rooms: int | None,
    attendees: int | None,
    equipment_request: str = "",
    note: str = "",
) -> dict:
    """生成预约草稿：包含解析结果、校验问题与摘要，不写数据库。"""
    problems: list[str] = []
    rooms = rooms or 1

    if venue is None:
        problems.append(
            f"没有找到名为「{venue_name}」的会议空间，请确认名称"
            if venue_name
            else "还需要确认预约哪个会议空间"
        )
    if meeting_room is None:
        problems.append("还需要确认会议室（例如西湖 A 会议室、路演厅）")
    if start_at is None:
        problems.append("还需要确认开始日期和时间")
    if end_at is None:
        problems.append("还需要确认结束时间或预约时长")
    if attendees is None:
        problems.append("还需要确认参会人数")
    if start_at and end_at and end_at <= start_at:
        problems.append("结束时间必须晚于开始时间")

    hours = (
        duration_hours(start_at, end_at)
        if start_at and end_at and end_at > start_at
        else None
    )
    price = float(meeting_room.hourly_price or 0) if meeting_room else 0
    total_amount = round(price * (hours or 0) * rooms, 2)

    if (
        not problems
        and venue
        and meeting_room
        and start_at
        and end_at
    ):
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
            "hourly_price": price,
            "total_amount": total_amount,
            "equipment_request": equipment_request or "",
        },
        "summary": "",
        "reservation_id": None,
    }
    draft["summary"] = summarize_draft(draft)
    return draft


def _format_datetime(value: str) -> str:
    try:
        target = datetime.fromisoformat(value)
    except ValueError:
        return value
    return target.strftime("%Y-%m-%d %H:%M")


def summarize_draft(draft: dict) -> str:
    payload = draft["payload"]
    if draft["problems"]:
        return "还差这些信息或需要调整：" + "；".join(draft["problems"])
    return (
        f"{payload['venue_name']}｜{payload['meeting_room_name']}｜"
        f"{_format_datetime(payload['start_at'])} 至 {_format_datetime(payload['end_at'])}，"
        f"共 {payload['hours']} 小时｜"
        f"{payload['rooms']} 间 / {payload['attendees']} 人｜"
        f"总价 ¥{payload['total_amount']:.0f}"
        + (
            f"｜设备需求：{payload['equipment_request']}"
            if payload["equipment_request"]
            else ""
        )
    )


def prepare_from_text(db: Session, user: User, text: str) -> dict:
    parsed = parse_reservation_text(db, text)
    note = ""
    if parsed.get("assumed_default_time"):
        note = "没有识别到具体开始时间，暂按 09:00、2 小时计算，请核对后调整。"
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
    meeting_room = (
        match_meeting_room(db, venue, str(arguments.get("meeting_room_name") or ""))
        or parsed.get("meeting_room")
    )

    start_at = (
        detect_datetime(str(arguments.get("start_at") or ""))
        or parsed.get("start_at")
    )
    end_at = (
        detect_datetime(str(arguments.get("end_at") or ""))
        or parsed.get("end_at")
    )

    hours = arguments.get("hours")
    try:
        hours = float(hours) if hours is not None else parsed.get("hours")
    except (TypeError, ValueError):
        hours = parsed.get("hours")
    if start_at and not end_at and hours:
        end_at = start_at + timedelta(hours=hours)

    def _int(value, fallback):
        try:
            return int(value) if value is not None else fallback
        except (TypeError, ValueError):
            return fallback

    rooms = _int(arguments.get("rooms"), parsed.get("rooms"))
    attendees = _int(arguments.get("attendees"), parsed.get("attendees"))
    equipment_request = (
        str(arguments.get("equipment_request") or "").strip()
        or parsed.get("equipment_request")
        or ""
    )

    return build_draft(
        db,
        user,
        venue=venue,
        venue_name=str(arguments.get("venue_name") or ""),
        meeting_room=meeting_room,
        start_at=start_at,
        end_at=end_at,
        rooms=rooms,
        attendees=attendees,
        equipment_request=equipment_request,
        note=(
            "没有识别到具体开始时间，暂按 09:00、2 小时计算，请核对后调整。"
            if parsed.get("assumed_default_time")
            else ""
        ),
    )


def confirm_draft(db: Session, user: User, draft: dict) -> Reservation:
    """用户确认后写入数据库，并重新执行完整时间、容量与库存校验。"""
    payload = draft.get("payload") or {}
    if not payload.get("venue_id") or not payload.get("meeting_room_id"):
        raise HTTPException(status_code=400, detail="预约信息不完整，请重新发起预约")

    reservation_payload = ReservationIn(
        venue_id=payload["venue_id"],
        meeting_room_id=payload["meeting_room_id"],
        start_at=datetime.fromisoformat(payload["start_at"]),
        end_at=datetime.fromisoformat(payload["end_at"]),
        rooms=int(payload.get("rooms") or 1),
        attendees=int(payload.get("attendees") or 1),
        equipment_request=(payload.get("equipment_request") or "")[:200],
    )
    return create_reservation(db, user, reservation_payload)
