"""Agent 可调用的工具集合：所有查询都按当前登录用户的权限范围返回数据。"""

import re
from datetime import date as date_type
from datetime import datetime, time, timedelta
from typing import Any, Callable, NamedTuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.knowledge import search_knowledge
from app.api.serializers import MEETING_ROOM_STATUS_TEXT, RESERVATION_STATUS_TEXT
from app.models import MeetingRoom, Reservation, User, Venue
from app.services.reservation_service import ACTIVE_STATUS, remaining_rooms

RESERVATION_RULES_TEXT = (
    "会议室预约规则：\n"
    "1. 开始时间不能早于当前时间，结束时间必须晚于开始时间；\n"
    "2. 预约时间支持分钟级精度；\n"
    "3. 预约必须处于空间开放时段内，常见开放时间为 08:00-21:00，以空间详情为准；\n"
    "4. 参会人数不能超过「会议室容纳人数 × 预约间数」；\n"
    "5. 时段重叠的待确认与已确认预约都会占用会议室；\n"
    "6. 费用 = 时租价 × 预约小时数 × 间数，提交前展示预估总价；\n"
    "7. 提交后状态为「待确认」，管理员确认后预约生效；\n"
    "8. 已确认预约开始后可以提前结束使用，系统会立即释放剩余会议室库存；\n"
    "9. 待确认或已确认预约可以取消，已拒绝、已取消、已完成的预约不能再操作。"
)


class _ToolArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SearchKnowledgeArgs(_ToolArgs):
    query: str = Field(description="检索关键词")


class ListVenuesArgs(_ToolArgs):
    keyword: str = Field(default="", description="按名称或地址过滤，可不填")
    city: str = Field(default="", description="按城市过滤，可不填")


class CheckMeetingRoomAvailabilityArgs(_ToolArgs):
    venue_name: str = Field(description="空间名称")
    start_at: str = Field(
        default="",
        description="开始时间，支持 ISO 时间、明天上午10点等口语表达",
    )
    end_at: str = Field(default="", description="结束时间，可不填（默认开始后 2 小时）")


class ListMyReservationsArgs(_ToolArgs):
    status: str = Field(
        default="",
        description="可选：pending 待确认、confirmed 已确认、rejected 已拒绝、canceled 已取消、completed 已完成",
    )


class NoToolArgs(_ToolArgs):
    pass


class PrepareReservationArgs(_ToolArgs):
    raw_text: str = Field(
        validation_alias=AliasChoices("raw_text", "text"),
        description="用户原始描述，用于补齐未结构化提供的信息",
    )
    venue_name: str = Field(default="", description="空间名称")
    meeting_room_name: str = Field(default="", description="会议室名称或布局")
    start_at: str = Field(default="", description="开始时间，例如 2026-11-06 10:00")
    end_at: str = Field(default="", description="结束时间")
    hours: float | None = Field(default=None, description="预约小时数，默认 2 小时")
    rooms: int | None = Field(default=None, description="预约间数，默认 1 间")
    attendees: int | None = Field(default=None, description="参会人数")
    equipment_request: str = Field(default="", description="设备或现场需求")


CN_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def cn_to_int(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = CN_DIGITS.get(left, 1) if left else 1
        ones = CN_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    total = 0
    for char in text:
        if char not in CN_DIGITS:
            return None
        total = total * 10 + CN_DIGITS[char]
    return total


def detect_date(value: str | None) -> date_type | None:
    text = (value or "").strip()
    if not text:
        return None
    today = date_type.today()
    relative = {
        "今天": 0,
        "今日": 0,
        "明天": 1,
        "明日": 1,
        "后天": 2,
        "大后天": 3,
    }
    for word, offset in relative.items():
        if word in text:
            return today + timedelta(days=offset)

    match = re.search(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})", text)
    if match:
        return date_type(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = re.search(r"(?<![\d:年-])(\d{1,2})\s*[-/月]\s*(\d{1,2})[日号]?", text)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        candidate = date_type(today.year, month, day)
        if candidate < today:
            candidate = date_type(today.year + 1, month, day)
        return candidate

    weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    match = re.search(r"(下周|下星期|本周|这周|周|星期)([一二三四五六日天])", text)
    if match:
        target = weekday_map[match.group(2)]
        if match.group(1).startswith("下"):
            next_monday = today + timedelta(days=7 - today.weekday())
            return next_monday + timedelta(days=target)
        offset = (target - today.weekday()) % 7
        return today + timedelta(days=offset or 7)

    try:
        return date_type.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_time_value(text: str) -> time | None:
    match = re.search(
        r"(?:(上午|早上|中午|下午|晚上)\s*)?(\d{1,2})(?::(\d{2}))?\s*(?:点|时|:(\d{2}))?",
        text,
    )
    if not match:
        return None
    hour = int(match.group(2))
    minute = int(match.group(3) or match.group(4) or 0)
    period = match.group(1) or ""
    if period in {"下午", "晚上"} and hour < 12:
        hour += 12
    if period == "中午" and hour < 11:
        hour += 12
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def detect_datetime(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    target_date = detect_date(text)
    target_time = _parse_time_value(text)
    if target_date is None or target_time is None:
        return None
    return datetime.combine(target_date, target_time)


def venue_aliases(venue: Venue) -> list[str]:
    name = (venue.name or "").replace(" ", "")
    if not name:
        return []
    short = name
    for suffix in (
        "会议空间",
        "共享会议室",
        "商务中心",
        "创新中心",
        "会议中心",
        "空间",
    ):
        if short.endswith(suffix) and len(short) > len(suffix):
            short = short[: -len(suffix)]
            break
    return list({item for item in (name, short) if len(item) >= 2})


def match_venue(db: Session, text: str) -> Venue | None:
    normalized = (text or "").replace(" ", "")
    if not normalized:
        return None
    matched: Venue | None = None
    matched_length = 0
    for venue in db.scalars(select(Venue)).all():
        for alias in venue_aliases(venue):
            if alias in normalized and len(alias) > matched_length:
                matched = venue
                matched_length = len(alias)
    return matched


def meeting_room_aliases(meeting_room: MeetingRoom) -> list[str]:
    name = (meeting_room.name or "").replace(" ", "")
    aliases = {name, (meeting_room.layout or "").replace(" ", "")}
    short = name
    for suffix in ("会议室", "多功能厅", "路演厅", "培训室", "讨论室"):
        if short.endswith(suffix) and len(short) > len(suffix):
            short = short[: -len(suffix)]
            break
    aliases.add(short)
    return [item for item in aliases if len(item) >= 2]


def match_meeting_room(
    db: Session, venue: Venue | None, text: str
) -> MeetingRoom | None:
    if venue is None:
        return None
    normalized = (text or "").replace(" ", "")
    matched: MeetingRoom | None = None
    matched_length = 0
    for meeting_room in db.scalars(
        select(MeetingRoom).where(MeetingRoom.venue_id == venue.id)
    ).all():
        for alias in meeting_room_aliases(meeting_room):
            if alias in normalized and len(alias) > matched_length:
                matched = meeting_room
                matched_length = len(alias)
    return matched


def _venue_brief(db: Session, venue: Venue) -> dict:
    count = (
        db.scalar(
            select(func.count(MeetingRoom.id)).where(MeetingRoom.venue_id == venue.id)
        )
        or 0
    )
    return {
        "name": venue.name,
        "city": venue.city,
        "address": venue.address,
        "rating": venue.rating,
        "room_count": venue.room_count,
        "open_time": venue.open_time,
        "close_time": venue.close_time,
        "status": "开放预约" if venue.status == 1 else "暂停开放",
        "meeting_room_count": count,
        "description": venue.description,
    }


def _reservation_brief(
    reservation: Reservation, venue_name: str = "", meeting_room_name: str = ""
) -> dict:
    return {
        "id": reservation.id,
        "venue_name": venue_name,
        "meeting_room_name": meeting_room_name,
        "start_at": reservation.start_at.isoformat(),
        "end_at": reservation.end_at.isoformat(),
        "hours": float(reservation.hours or 0),
        "rooms": reservation.rooms,
        "attendees": reservation.attendees,
        "total_amount": float(reservation.total_amount or 0),
        "equipment_request": reservation.equipment_request,
        "status": RESERVATION_STATUS_TEXT.get(reservation.status, reservation.status),
        "remark": reservation.remark,
    }


def _reservation_names(db: Session, reservation: Reservation) -> tuple[str, str]:
    venue = db.get(Venue, reservation.venue_id)
    meeting_room = db.get(MeetingRoom, reservation.meeting_room_id)
    return (venue.name if venue else ""), (
        meeting_room.name if meeting_room else ""
    )


def search_knowledge_tool(db: Session, query: str) -> dict:
    results = search_knowledge(db, query, limit=3)
    if not results:
        results = search_knowledge(db, query, limit=3, min_score=0.15)
    return {
        "results": [
            {
                "category": item["category"],
                "question": item["question"],
                "answer": item["answer"],
            }
            for item in results
        ]
    }


def list_venues_tool(db: Session, keyword: str = "", city: str = "") -> dict:
    venues = db.scalars(select(Venue).order_by(Venue.id.asc())).all()
    if keyword:
        text = keyword.strip()
        venues = [
            item for item in venues if text in item.name or text in item.address
        ]
    if city:
        venues = [item for item in venues if city in item.city]
    return {"venues": [_venue_brief(db, item) for item in venues]}


def check_meeting_room_availability_tool(
    db: Session, venue_name: str, start_at: str = "", end_at: str = ""
) -> dict:
    venue = match_venue(db, venue_name)
    if venue is None:
        return {
            "error": "没有匹配到会议空间，请确认名称",
            "available_venues": [
                item.name for item in db.scalars(select(Venue)).all()
            ],
        }

    start = detect_datetime(start_at)
    if start is None:
        start = datetime.combine(date_type.today() + timedelta(days=1), time(9, 0))
    end = detect_datetime(end_at)
    if end is None or end <= start:
        end = start + timedelta(hours=2)

    meeting_rooms = db.scalars(
        select(MeetingRoom)
        .where(MeetingRoom.venue_id == venue.id)
        .order_by(MeetingRoom.hourly_price.asc())
    ).all()
    return {
        "venue_name": venue.name,
        "city": venue.city,
        "address": venue.address,
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "hours": round((end - start).total_seconds() / 3600, 2),
        "open_time": venue.open_time,
        "close_time": venue.close_time,
        "status": "开放预约" if venue.status == 1 else "暂停开放",
        "meeting_rooms": [
            {
                "name": item.name,
                "layout": item.layout,
                "hourly_price": float(item.hourly_price or 0),
                "capacity": item.capacity,
                "quantity": item.quantity,
                "equipment": item.equipment,
                "remaining": remaining_rooms(db, item, start, end),
                "status": MEETING_ROOM_STATUS_TEXT.get(item.status, item.status),
            }
            for item in meeting_rooms
        ],
    }


def list_my_reservations_tool(db: Session, user: User, status_text: str = "") -> dict:
    conditions = [Reservation.user_id == user.id]
    if status_text:
        matched = [
            key for key, value in RESERVATION_STATUS_TEXT.items() if value == status_text
        ]
        matched += [key for key in RESERVATION_STATUS_TEXT if key == status_text]
        conditions.append(Reservation.status.in_(matched or [status_text]))

    reservations = db.scalars(
        select(Reservation)
        .where(*conditions)
        .order_by(Reservation.start_at.desc(), Reservation.id.desc())
        .limit(10)
    ).all()
    items = []
    for reservation in reservations:
        venue_name, meeting_room_name = _reservation_names(db, reservation)
        items.append(
            _reservation_brief(reservation, venue_name, meeting_room_name)
        )
    return {"total": len(items), "reservations": items}


def list_pending_reservations_tool(db: Session, user: User) -> dict:
    if user.role != "admin":
        return {
            "error": "只有空间管理员可以查看全部待确认预约，普通用户只能查看自己的预约"
        }

    reservations = db.scalars(
        select(Reservation)
        .where(Reservation.status == "pending")
        .order_by(Reservation.start_at.asc(), Reservation.id.asc())
        .limit(20)
    ).all()
    items = []
    for reservation in reservations:
        venue_name, meeting_room_name = _reservation_names(db, reservation)
        brief = _reservation_brief(reservation, venue_name, meeting_room_name)
        applicant = db.get(User, reservation.user_id)
        brief["member"] = (
            (applicant.name or applicant.username) if applicant else ""
        )
        items.append(brief)
    return {"total": len(items), "reservations": items}


def system_statistics_tool(db: Session, user: User) -> dict:
    is_admin = user.role == "admin"
    scope = [] if is_admin else [Reservation.user_id == user.id]
    today = date_type.today()
    day_start = datetime.combine(today, time.min)
    day_end = day_start + timedelta(days=1)
    total_rooms = (
        db.scalar(select(func.coalesce(func.sum(MeetingRoom.quantity), 0))) or 0
    )
    occupied_today = (
        db.scalar(
            select(func.coalesce(func.sum(Reservation.rooms), 0)).where(
                Reservation.status.in_(ACTIVE_STATUS),
                Reservation.start_at < day_end,
                Reservation.end_at > day_start,
            )
        )
        or 0
    )
    return {
        "venue_total": db.scalar(select(func.count(Venue.id))) or 0,
        "meeting_room_total": db.scalar(select(func.count(MeetingRoom.id))) or 0,
        "user_total": (
            (db.scalar(select(func.count(User.id))) or 0)
            if is_admin
            else "无权限查看"
        ),
        "reservation_total": db.scalar(
            select(func.count(Reservation.id)).where(*scope)
        )
        or 0,
        "pending_total": db.scalar(
            select(func.count(Reservation.id)).where(
                *scope, Reservation.status == "pending"
            )
        )
        or 0,
        "utilization_rate": (
            round(occupied_today * 100 / total_rooms) if total_rooms else 0
        ),
        "scope": (
            "全部空间数据"
            if is_admin
            else "仅统计当前登录用户的预约"
        ),
    }


def reservation_rules_tool() -> dict:
    return {"rules": RESERVATION_RULES_TEXT}


class ToolSpec(NamedTuple):
    description: str
    args: type[_ToolArgs]
    handler: Callable[[Session, User, Any], dict]


def _handle_search_knowledge(
    db: Session, user: User, args: SearchKnowledgeArgs
) -> dict:
    return search_knowledge_tool(db, args.query)


def _handle_list_venues(
    db: Session, user: User, args: ListVenuesArgs
) -> dict:
    return list_venues_tool(db, args.keyword, args.city)


def _handle_check_meeting_room_availability(
    db: Session, user: User, args: CheckMeetingRoomAvailabilityArgs
) -> dict:
    return check_meeting_room_availability_tool(
        db, args.venue_name, args.start_at, args.end_at
    )


def _handle_list_my_reservations(
    db: Session, user: User, args: ListMyReservationsArgs
) -> dict:
    return list_my_reservations_tool(db, user, args.status)


def _handle_list_pending_reservations(
    db: Session, user: User, args: NoToolArgs
) -> dict:
    return list_pending_reservations_tool(db, user)


def _handle_system_statistics(
    db: Session, user: User, args: NoToolArgs
) -> dict:
    return system_statistics_tool(db, user)


def _handle_reservation_rules(
    db: Session, user: User, args: NoToolArgs
) -> dict:
    return reservation_rules_tool()


def _handle_prepare_reservation(
    db: Session, user: User, args: PrepareReservationArgs
) -> dict:
    from app.agent.reservation import prepare_from_arguments

    return prepare_from_arguments(db, user, args.model_dump())


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_knowledge": ToolSpec(
        "检索会议室预约知识库（预约流程、时段冲突、容量、设备与发票等问题）",
        SearchKnowledgeArgs,
        _handle_search_knowledge,
    ),
    "list_venues": ToolSpec(
        "查询会议空间列表，含城市、地址、开放时段、会议室数量和状态",
        ListVenuesArgs,
        _handle_list_venues,
    ),
    "check_meeting_room_availability": ToolSpec(
        "查询某空间在指定起止时间内的会议室、时租价、容量与剩余数量",
        CheckMeetingRoomAvailabilityArgs,
        _handle_check_meeting_room_availability,
    ),
    "list_my_reservations": ToolSpec(
        "查询当前登录用户自己的会议室预约与状态",
        ListMyReservationsArgs,
        _handle_list_my_reservations,
    ),
    "list_pending_reservations": ToolSpec(
        "查询待确认预约列表，仅管理员可用",
        NoToolArgs,
        _handle_list_pending_reservations,
    ),
    "system_statistics": ToolSpec(
        "查询经营统计：空间数、会议室规格数、预约数、待确认数、今日预约与使用率",
        NoToolArgs,
        _handle_system_statistics,
    ),
    "reservation_rules": ToolSpec(
        "获取会议室预约规则（开放时间、容量、计费、取消政策）",
        NoToolArgs,
        _handle_reservation_rules,
    ),
    "prepare_reservation": ToolSpec(
        "根据用户需求生成预约预览卡片。不会真正写入数据库，"
        "用户点击「确认预约」后才会创建预约；缺少信息或余量不足时在 problems 中说明。",
        PrepareReservationArgs,
        _handle_prepare_reservation,
    ),
}


def _strip_titles(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            key: _strip_titles(value)
            for key, value in node.items()
            if key != "title"
        }
    if isinstance(node, list):
        return [_strip_titles(item) for item in node]
    return node


def _tool_schema(name: str, spec: ToolSpec) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": spec.description,
            "parameters": _strip_titles(spec.args.model_json_schema()),
        },
    }


TOOL_SCHEMAS = [
    _tool_schema(name, spec) for name, spec in TOOL_REGISTRY.items()
]
TOOL_NAMES = list(TOOL_REGISTRY)


def _format_validation_error(error: ValidationError) -> str:
    parts = []
    for item in error.errors()[:4]:
        location = ".".join(str(part) for part in item.get("loc") or ()) or "参数"
        parts.append(f"{location}: {item.get('msg', '不合法')}")
    return "；".join(parts) or "参数不合法"


def execute_tool(name: str, arguments: dict, db: Session, user: User) -> dict:
    """校验模型参数后执行工具，并把参数错误作为结果交还给模型。"""
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        return {"error": f"未知工具：{name}"}

    try:
        args = spec.args.model_validate(arguments or {})
    except ValidationError as error:
        return {
            "error": f"工具 {name} 的参数不合法：{_format_validation_error(error)}"
        }

    return spec.handler(db, user, args)
