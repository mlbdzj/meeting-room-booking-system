"""客服助手可调用的工具集合：所有查询都按当前登录用户的权限范围返回数据。"""

import re
from datetime import date as date_type
from datetime import timedelta

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

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "检索会议空间客服知识库（使用开始使用结束、押金发票、取消政策、会员等问题）",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "检索关键词"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_venues",
            "description": "查询会议空间列表，含城市、地址、星级、会议室类型数量与营业状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "按名称或地址过滤，可不填"},
                    "city": {"type": "string", "description": "按城市过滤，可不填"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_room_availability",
            "description": "查询某会议空间在指定使用开始/使用结束日期内的会议室类型、价格与剩余会议室余量，用于判断还能不能订",
            "parameters": {
                "type": "object",
                "properties": {
                    "venue_name": {"type": "string", "description": "会议空间名称"},
                    "check_in": {"type": "string", "description": "使用开始日期，支持 2026-09-23 / 明天 / 下周五"},
                    "check_out": {"type": "string", "description": "使用结束日期，可不填（默认使用开始后 1 晚）"},
                },
                "required": ["venue_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_reservations",
            "description": "查询当前登录用户自己的预约与状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "可选过滤：pending 待确认、confirmed 已确认、rejected 已拒绝、canceled 已取消、completed 已完成",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pending_reservations",
            "description": "查询待确认预约列表，仅管理员可用",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_statistics",
            "description": "查询经营统计：会议空间数、会议室类型数、预约数、待确认数、今日使用开始与使用开始率",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reservation_rules",
            "description": "获取会议空间预约规则（使用开始使用结束时间、会议室余量、人数、取消政策）",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_reservation",
            "description": (
                "根据用户需求生成预约预览卡片。注意：这不会真正下单，"
                "系统会把预览展示成卡片，用户点击「确认下单」后才会创建预约；"
                "缺少信息或会议室余量不足时会在 problems 中说明。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "raw_text": {"type": "string", "description": "用户的原始描述，用于补齐未结构化提供的信息"},
                    "venue_name": {"type": "string", "description": "会议空间名称"},
                    "meeting_room_name": {"type": "string", "description": "会议室类型名称，例如「大床房」「双床房」"},
                    "check_in": {"type": "string", "description": "使用开始日期，支持 2026-09-23 / 明天 / 下周五"},
                    "check_out": {"type": "string", "description": "使用结束日期，可不填"},
                    "hours": {"type": "integer", "description": "使用开始晚数，缺省按 1 晚"},
                    "rooms": {"type": "integer", "description": "预约间数，缺省 1 间"},
                    "attendees": {"type": "integer", "description": "使用开始人数"},
                    "equipment_request": {"type": "string", "description": "特殊要求，例如「安静楼层」「加床」"},
                },
                "required": ["raw_text"],
            },
        },
    },
]

TOOL_NAMES = [item["function"]["name"] for item in TOOL_SCHEMAS]


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


def execute_tool(name: str, arguments: dict, db: Session, user: User) -> dict:
    arguments = arguments or {}
    if name == "search_knowledge":
        return search_knowledge_tool(db, str(arguments.get("query", "")))
    if name == "list_venues":
        return list_venues_tool(db, str(arguments.get("keyword", "") or ""), str(arguments.get("city", "") or ""))
    if name == "check_room_availability":
        return check_room_availability_tool(
            db,
            str(arguments.get("venue_name", "")),
            str(arguments.get("check_in", "") or ""),
            str(arguments.get("check_out", "") or ""),
        )
    if name == "list_my_reservations":
        return list_my_reservations_tool(db, user, str(arguments.get("status", "") or ""))
    if name == "list_pending_reservations":
        return list_pending_reservations_tool(db, user)
    if name == "system_statistics":
        return system_statistics_tool(db, user)
    if name == "reservation_rules":
        return reservation_rules_tool()
    if name == "prepare_reservation":
        from app.agent.reservation import prepare_from_arguments

        return prepare_from_arguments(db, user, arguments)
    return {"error": f"未知工具：{name}"}
