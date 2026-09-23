"""客服助手可调用的工具集合：所有查询都按当前登录用户的权限范围返回数据。"""

import re
from datetime import date as date_type
from datetime import timedelta
from typing import Any, Callable, NamedTuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.knowledge import search_knowledge
from app.api.serializers import RESERVATION_STATUS_TEXT, MEETING_ROOM_STATUS_TEXT
from app.db.session import SessionLocal
from app.models import Reservation, Venue, MeetingRoom, User
from app.services.reservation_service import ACTIVE_STATUS, remaining_rooms

RESERVATION_RULES_TEXT = (
    "预约规则：\n"
    "1. 使用开始日期不能早于今天，使用结束日期必须晚于使用开始日期，最少使用开始 1 晚；\n"
    "2. 使用开始时间通常为 14:00 之后，使用结束时间为 12:00 之前，具体以会议空间说明为准；\n"
    "3. 下单需选择会议室类型与间数，间数不能超过该会议室类型在使用开始日期内的剩余会议室余量；\n"
    "4. 使用开始人数不能超过「会议室类型可住人数 × 间数」，超员建议加订房间；\n"
    "5. 房费 = 会议室类型单价 × 晚数 × 间数，下单时会自动计算总价；\n"
    "6. 提交后预约状态为「待确认」，会议空间确认后预约生效；\n"
    "7. 待确认、已确认的预约可以取消；已拒绝、已取消、已完成的预约不可再操作。"
)

class _ToolArgs(BaseModel):
    """工具入参基类：模型多传的字段直接忽略，不因为无关字段让整次调用失败。"""

    model_config = ConfigDict(extra="ignore")


class SearchKnowledgeArgs(_ToolArgs):
    query: str = Field(description="检索关键词")


class ListVenuesArgs(_ToolArgs):
    keyword: str = Field(default="", description="按名称或地址过滤，可不填")
    city: str = Field(default="", description="按城市过滤，可不填")


class CheckRoomAvailabilityArgs(_ToolArgs):
    venue_name: str = Field(description="会议空间名称")
    check_in: str = Field(default="", description="使用开始日期，支持 2026-09-23 / 明天 / 下周五")
    check_out: str = Field(default="", description="使用结束日期，可不填（默认使用开始后 1 晚）")


class ListMyReservationsArgs(_ToolArgs):
    status: str = Field(
        default="",
        description="可选过滤：pending 待确认、confirmed 已确认、rejected 已拒绝、canceled 已取消、completed 已完成",
    )


# 无入参工具：list_pending_reservations / system_statistics / reservation_rules
class NoToolArgs(_ToolArgs):
    pass


class PrepareReservationArgs(_ToolArgs):
    raw_text: str = Field(
        validation_alias=AliasChoices("raw_text", "text"),
        description="用户的原始描述，用于补齐未结构化提供的信息",
    )
    venue_name: str = Field(default="", description="会议空间名称")
    meeting_room_name: str = Field(default="", description="会议室类型名称，例如「大床房」「双床房」")
    check_in: str = Field(default="", description="使用开始日期，支持 2026-09-23 / 明天 / 下周五")
    check_out: str = Field(default="", description="使用结束日期，可不填")
    hours: int | None = Field(default=None, description="使用开始晚数，缺省按 1 晚")
    rooms: int | None = Field(default=None, description="预约间数，缺省 1 间")
    attendees: int | None = Field(default=None, description="使用开始人数")
    equipment_request: str = Field(default="", description="特殊要求，例如「安静楼层」「加床」")


def resolve_date(value: str | None) -> date_type:
    """把「今天/明天/下周五/9月24号」等写法解析成日期，解析不到时返回今天。"""
    return detect_date(value) or date_type.today()


def detect_date(value: str | None) -> date_type | None:
    text = (value or "").strip()
    if not text:
        return None
    today = date_type.today()
    relative = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2, "大后天": 3}
    for word, offset in relative.items():
        if word in text:
            return today + timedelta(days=offset)

    match = re.search(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})", text)
    if match:
        return date_type(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = re.search(r"(\d{1,2})\s*[-/月]\s*(\d{1,2})[日号]?", text)
    if match:
        return date_type(today.year, int(match.group(1)), int(match.group(2)))

    weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    match = re.search(r"(下周|下星期|本周|这周|周|星期)([一二三四五六日天])", text)
    if match:
        target = weekday_map[match.group(2)]
        if match.group(1).startswith("下"):
            # 下周X：先跳到下周一，再加上星期偏移
            next_monday = today + timedelta(days=7 - today.weekday())
            return next_monday + timedelta(days=target)
        offset = (target - today.weekday()) % 7
        return today + timedelta(days=offset or 7)

    try:
        return date_type.fromisoformat(text)
    except ValueError:
        return None


def venue_aliases(venue: Venue) -> list[str]:
    name = (venue.name or "").replace(" ", "")
    if not name:
        return []
    short = name
    for suffix in ("假日会议空间", "大会议空间", "会议空间", "宾馆", "公寓"):
        if short.endswith(suffix) and len(short) > len(suffix):
            short = short[: -len(suffix)]
            break
    aliases = {name, short}
    return [item for item in aliases if len(item) >= 2]


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


def _venue_brief(db: Session, venue: Venue) -> dict:
    meeting_room_count = db.scalar(select(func.count(MeetingRoom.id)).where(MeetingRoom.venue_id == venue.id)) or 0
    return {
        "name": venue.name,
        "city": venue.city,
        "address": venue.address,
        "star": venue.star,
        "room_count": venue.room_count,
        "open_time": venue.open_time,
        "close_time": venue.close_time,
        "status": "营业中" if venue.status == 1 else "暂停营业",
        "meeting_room_count": meeting_room_count,
        "description": venue.description,
    }


def _reservation_brief(reservation: Reservation, venue_name: str = "", meeting_room_name: str = "") -> dict:
    return {
        "id": reservation.id,
        "venue_name": venue_name,
        "meeting_room_name": meeting_room_name,
        "start_at": reservation.start_at.isoformat(),
        "end_at": reservation.end_at.isoformat(),
        "hours": reservation.hours,
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
    return (venue.name if venue else ""), (meeting_room.name if meeting_room else "")


def search_knowledge_tool(db: Session, query: str) -> dict:
    results = search_knowledge(db, query, limit=3)
    if not results:
        results = search_knowledge(db, query, limit=3, min_score=0.15)
    return {
        "results": [
            {"category": item["category"], "question": item["question"], "answer": item["answer"]}
            for item in results
        ]
    }


def list_venues_tool(db: Session, keyword: str = "", city: str = "") -> dict:
    venues = db.scalars(select(Venue).order_by(Venue.id.asc())).all()
    if keyword:
        text = keyword.strip()
        venues = [item for item in venues if text in item.name or text in item.address]
    if city:
        venues = [item for item in venues if city in item.city]
    return {"venues": [_venue_brief(db, item) for item in venues]}


def check_room_availability_tool(
    db: Session, venue_name: str, check_in: str = "", check_out: str = ""
) -> dict:
    venue = match_venue(db, venue_name)
    if venue is None:
        return {
            "error": "没有匹配到会议空间，请确认名称",
            "available_venues": [item.name for item in db.scalars(select(Venue)).all()],
        }

    start = resolve_date(check_in)
    end = detect_date(check_out) if check_out else None
    if end is None or end <= start:
        end = start + timedelta(days=1)

    meeting_rooms = db.scalars(
        select(MeetingRoom).where(MeetingRoom.venue_id == venue.id).order_by(MeetingRoom.price.asc())
    ).all()
    return {
        "venue_name": venue.name,
        "city": venue.city,
        "address": venue.address,
        "check_in": start.isoformat(),
        "check_out": end.isoformat(),
        "hours": (end - start).days,
        "open_time": venue.open_time,
        "close_time": venue.close_time,
        "status": "营业中" if venue.status == 1 else "暂停营业",
        "meeting_rooms": [
            {
                "name": item.name,
                "layout": item.layout,
                "price": float(item.price or 0),
                "capacity": item.capacity,
                "quantity": item.quantity,
                "remaining": remaining_rooms(db, item, start, end),
                "status": MEETING_ROOM_STATUS_TEXT.get(item.status, item.status),
            }
            for item in meeting_rooms
        ],
    }


def list_my_reservations_tool(db: Session, user: User, status_text: str = "") -> dict:
    conditions = [Reservation.user_id == user.id]
    if status_text:
        matched = [key for key, value in RESERVATION_STATUS_TEXT.items() if value == status_text]
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
        items.append(_reservation_brief(reservation, venue_name, meeting_room_name))
    return {"total": len(items), "reservations": items}


def list_pending_reservations_tool(db: Session, user: User) -> dict:
    if user.role != "admin":
        return {"error": "只有空间管理员可以查看全部待确认预约，普通用户只能查看自己的预约"}

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
        brief["guest"] = (applicant.name or applicant.username) if applicant else ""
        items.append(brief)
    return {"total": len(items), "reservations": items}


def system_statistics_tool(db: Session, user: User) -> dict:
    is_admin = user.role == "admin"
    scope = [] if is_admin else [Reservation.user_id == user.id]
    today = date_type.today()
    total_rooms = db.scalar(select(func.coalesce(func.sum(MeetingRoom.quantity), 0))) or 0
    occupied_today = (
        db.scalar(
            select(func.coalesce(func.sum(Reservation.rooms), 0)).where(
                Reservation.status.in_(ACTIVE_STATUS),
                Reservation.start_at <= today,
                Reservation.end_at > today,
            )
        )
        or 0
    )
    return {
        "venue_total": db.scalar(select(func.count(Venue.id))) or 0,
        "meeting_room_total": db.scalar(select(func.count(MeetingRoom.id))) or 0,
        "user_total": (db.scalar(select(func.count(User.id))) or 0) if is_admin else "无权限查看",
        "reservation_total": db.scalar(select(func.count(Reservation.id)).where(*scope)) or 0,
        "pending_total": db.scalar(
            select(func.count(Reservation.id)).where(*scope, Reservation.status == "pending")
        )
        or 0,
        "occupancy_rate": round(occupied_today * 100 / total_rooms) if total_rooms else 0,
        "scope": "全部空间数据" if is_admin else "仅统计当前登录用户的预约",
    }


def reservation_rules_tool() -> dict:
    return {"rules": RESERVATION_RULES_TEXT}


# ===== 工具注册表 =====
# 名称 / 描述 / 入参模型 / 处理器集中在这里，新增一个工具要同时改三处：
# 入参模型、适配器、注册表条目。发给模型的 JSON Schema 由入参模型自动生成。


class ToolSpec(NamedTuple):
    description: str
    args: type[_ToolArgs]
    handler: Callable[[Session, User, Any], dict]


def _handle_search_knowledge(db: Session, user: User, args: SearchKnowledgeArgs) -> dict:
    return search_knowledge_tool(db, args.query)


def _handle_list_venues(db: Session, user: User, args: ListVenuesArgs) -> dict:
    return list_venues_tool(db, args.keyword, args.city)


def _handle_check_room_availability(db: Session, user: User, args: CheckRoomAvailabilityArgs) -> dict:
    return check_room_availability_tool(db, args.venue_name, args.check_in, args.check_out)


def _handle_list_my_reservations(db: Session, user: User, args: ListMyReservationsArgs) -> dict:
    return list_my_reservations_tool(db, user, args.status)


def _handle_list_pending_reservations(db: Session, user: User, args: NoToolArgs) -> dict:
    return list_pending_reservations_tool(db, user)


def _handle_system_statistics(db: Session, user: User, args: NoToolArgs) -> dict:
    return system_statistics_tool(db, user)


def _handle_reservation_rules(db: Session, user: User, args: NoToolArgs) -> dict:
    return reservation_rules_tool()


def _handle_prepare_reservation(db: Session, user: User, args: PrepareReservationArgs) -> dict:
    # 延迟导入：reservation.py 反向依赖本模块的 detect_date / match_venue
    from app.agent.reservation import prepare_from_arguments

    return prepare_from_arguments(db, user, args.model_dump())


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_knowledge": ToolSpec(
        "检索会议空间客服知识库（使用开始使用结束、押金发票、取消政策、会员等问题）",
        SearchKnowledgeArgs,
        _handle_search_knowledge,
    ),
    "list_venues": ToolSpec(
        "查询会议空间列表，含城市、地址、星级、会议室类型数量与营业状态",
        ListVenuesArgs,
        _handle_list_venues,
    ),
    "check_room_availability": ToolSpec(
        "查询某会议空间在指定使用开始/使用结束日期内的会议室类型、价格与剩余会议室余量，用于判断还能不能订",
        CheckRoomAvailabilityArgs,
        _handle_check_room_availability,
    ),
    "list_my_reservations": ToolSpec(
        "查询当前登录用户自己的预约与状态",
        ListMyReservationsArgs,
        _handle_list_my_reservations,
    ),
    "list_pending_reservations": ToolSpec(
        "查询待确认预约列表，仅管理员可用",
        NoToolArgs,
        _handle_list_pending_reservations,
    ),
    "system_statistics": ToolSpec(
        "查询经营统计：会议空间数、会议室类型数、预约数、待确认数、今日使用开始与使用开始率",
        NoToolArgs,
        _handle_system_statistics,
    ),
    "reservation_rules": ToolSpec(
        "获取会议空间预约规则（使用开始使用结束时间、会议室余量、人数、取消政策）",
        NoToolArgs,
        _handle_reservation_rules,
    ),
    "prepare_reservation": ToolSpec(
        "根据用户需求生成预约预览卡片。注意：这不会真正下单，"
        "系统会把预览展示成卡片，用户点击「确认下单」后才会创建预约；"
        "缺少信息或会议室余量不足时会在 problems 中说明。",
        PrepareReservationArgs,
        _handle_prepare_reservation,
    ),
}


def _strip_titles(node: Any) -> Any:
    """去掉 Pydantic 自动补的 title，只保留 type / description / default 这些对模型有用的字段。"""
    if isinstance(node, dict):
        return {key: _strip_titles(value) for key, value in node.items() if key != "title"}
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


TOOL_SCHEMAS = [_tool_schema(name, spec) for name, spec in TOOL_REGISTRY.items()]
TOOL_NAMES = list(TOOL_REGISTRY)


def _format_validation_error(error: ValidationError) -> str:
    parts = []
    for item in error.errors()[:4]:
        location = ".".join(str(part) for part in item.get("loc") or ()) or "参数"
        parts.append(f"{location}: {item.get('msg', '不合法')}")
    return "；".join(parts) or "参数不合法"


def execute_tool(name: str, arguments: dict, db: Session, user: User) -> dict:
    """校验模型给的参数后执行工具。

    参数不合契约时把原因作为工具结果回给模型（而不是抛异常），模型可以据此重新调用。
    """
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        return {"error": f"未知工具：{name}"}

    try:
        args = spec.args.model_validate(arguments or {})
    except ValidationError as error:
        return {"error": f"工具 {name} 的参数不合法：{_format_validation_error(error)}"}

    return spec.handler(db, user, args)
