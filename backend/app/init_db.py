"""初始化会议室预约系统的表结构与演示数据。"""

import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, inspect, select, text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import Knowledge, MeetingRoom, Reservation, User, Venue

logger = logging.getLogger("meeting-room-agent")

VENUE_SEEDS = [
    {
        "name": "杭州西湖商务中心",
        "city": "杭州",
        "address": "西湖区文三路 88 号",
        "rating": 5,
        "room_count": 12,
        "open_time": "08:30",
        "close_time": "20:00",
        "description": "近地铁与西湖景区，提供接待区、打印服务和视频会议支持。",
    },
    {
        "name": "上海外滩云舍会议空间",
        "city": "上海",
        "address": "黄浦区中山东一路 12 号",
        "rating": 4,
        "room_count": 9,
        "open_time": "09:00",
        "close_time": "19:00",
        "description": "位于外滩核心区，适合商务洽谈、客户演示和中小型培训。",
    },
    {
        "name": "成都宽窄巷子共享会议室",
        "city": "成都",
        "address": "青羊区长顺上街 66 号",
        "rating": 4,
        "room_count": 8,
        "open_time": "09:00",
        "close_time": "18:00",
        "description": "庭院式共享办公空间，支持茶歇、白板讨论和团队工作坊。",
    },
    {
        "name": "深圳湾创新中心",
        "city": "深圳",
        "address": "南山区科苑南路 20 号",
        "rating": 5,
        "room_count": 16,
        "open_time": "08:00",
        "close_time": "21:00",
        "description": "面向科技团队的会议中心，配备直播、投屏和远程协作设备。",
    },
]

# (空间名, 会议室名, 编号, 布局, 时租价, 容纳人数, 数量, 设备, 状态, 描述)
MEETING_ROOM_SEEDS = [
    ("杭州西湖商务中心", "西湖 A 会议室", "MR-HZ-001", "课桌式", 120, 12, 3, "投影、白板、视频会议", "open", "适合项目评审与小型培训。"),
    ("杭州西湖商务中心", "西湖 B 会议室", "MR-HZ-002", "U 型", 160, 20, 2, "双屏、无线投屏、白板", "open", "适合客户洽谈与团队讨论。"),
    ("杭州西湖商务中心", "钱塘多功能厅", "MR-HZ-003", "剧院式", 320, 60, 1, "LED 屏、音响、直播", "open", "可分隔为两个独立讨论区。"),
    ("上海外滩云舍会议空间", "外滩 1 号", "MR-SH-001", "董事会式", 260, 16, 2, "视频会议、电子白板", "open", "高层景观，适合客户演示。"),
    ("上海外滩云舍会议空间", "外滩 2 号", "MR-SH-002", "岛式", 220, 24, 2, "投影、音响、直播", "open", "可灵活拆分小组讨论。"),
    ("上海外滩云舍会议空间", "浦江路演厅", "MR-SH-003", "剧院式", 480, 80, 1, "LED 屏、舞台、直播", "maintenance", "路演厅设备升级中。"),
    ("成都宽窄巷子共享会议室", "宽巷子 1 号", "MR-CD-001", "圆桌式", 98, 10, 3, "电视、白板、打印", "open", "自然采光，适合创意讨论。"),
    ("成都宽窄巷子共享会议室", "窄巷子培训室", "MR-CD-002", "课桌式", 180, 30, 2, "投影、音响、白板", "open", "适合内部培训与工作坊。"),
    ("深圳湾创新中心", "南山 A 会议室", "MR-SZ-001", "U 型", 180, 18, 4, "双屏、视频会议、白板", "open", "适合跨团队周会与面试。"),
    ("深圳湾创新中心", "前海路演厅", "MR-SZ-002", "剧院式", 520, 100, 1, "LED 屏、舞台、直播、同传", "open", "支持百人发布活动。"),
    ("深圳湾创新中心", "大鹏头脑风暴室", "MR-SZ-003", "岛式", 150, 16, 3, "移动屏、白板墙", "closed", "该房间正在改造，暂停预约。"),
]

KNOWLEDGE_SEEDS = [
    {
        "category": "预约流程",
        "question": "怎么预约会议室？",
        "answer": "进入「空间管理」选择空间，点击「立即预约」，选择开始时间、结束时间、会议室、间数和参会人数后提交。提交后状态为「待确认」，管理员确认后预约生效。也可以直接告诉智能助手，例如「帮我订下周五上午10点到12点的西湖 A 会议室，10人」。",
        "keywords": "预约,怎么约,订会议室,预约会议,下单",
    },
    {
        "category": "预约流程",
        "question": "在哪里查看我的预约？",
        "answer": "点击左侧「我的预约」，可以按状态查看空间、会议室、起止时间、时长、总价和确认意见。待确认或已确认的预约可直接取消。",
        "keywords": "我的预约,预约记录,查看预约,预约状态",
    },
    {
        "category": "预约流程",
        "question": "空间开放时间是几点？",
        "answer": "不同空间开放时间不同，杭州西湖商务中心为 08:30-20:00，上海为 09:00-19:00，成都为 09:00-18:00，深圳为 08:00-21:00。预约起止时间必须处于所选空间的开放时段内。",
        "keywords": "开放时间,营业时间,几点开门,几点关门",
    },
    {
        "category": "预约流程",
        "question": "预约提交后多久会被确认？",
        "answer": "系统不会自动确认，需要空间管理员在「预约审核」页面处理。建议至少提前一天预约，临近开始时间的预约会优先处理。",
        "keywords": "多久确认,确认时间,什么时候确认",
    },
    {
        "category": "预约流程",
        "question": "怎么取消预约？",
        "answer": "在「我的预约」找到状态为「待确认」或「已确认」的预约，点击「取消预约」并确认。已拒绝、已取消、已完成的预约不能再次操作。",
        "keywords": "取消预约,退订,取消会议,不去了",
    },
    {
        "category": "预约流程",
        "question": "预约被拒绝了怎么办？",
        "answer": "可以在「确认意见」中查看拒绝原因，例如时段冲突、参会人数超出容量或设备不可用。调整时间、会议室或人数后重新预约即可。",
        "keywords": "拒绝,被拒,预约被拒,确认意见",
    },
    {
        "category": "会议室与容量",
        "question": "会议室剩余数量怎么看？",
        "answer": "在预约弹窗中选择空间和起止时间后，会实时显示每种会议室的剩余数量。待确认与已确认预约都会占用库存，时段重叠时不会重复分配。",
        "keywords": "剩余会议室,库存,还有会议室吗,满房,时段冲突",
    },
    {
        "category": "会议室与容量",
        "question": "一个会议室能坐多少人？",
        "answer": "以会议室的「容纳人数」为准。参会人数不能超过「单间容量 × 预约间数」。人数较多时，可以增加会议室数量或选择多功能厅。",
        "keywords": "容纳人数,坐几个人,参会人数,超出容量",
    },
    {
        "category": "会议室与容量",
        "question": "预约费用怎么计算？",
        "answer": "总价 = 会议室时租价 × 预约小时数 × 间数。系统按分钟精确计算时长，例如 2.5 小时会按 2.5 小时计费，提交前会展示预估总价。",
        "keywords": "价格,费用,多少钱,时租,总价,计算",
    },
    {
        "category": "会议室与容量",
        "question": "可以预约多间会议室吗？",
        "answer": "可以。同一会议室规格剩余数量足够时，可在预约表单中填写间数。拆分会、分组讨论等场景也可以分两次提交不同会议室的预约。",
        "keywords": "多间会议室,两间,分组,拆分会议",
    },
    {
        "category": "设备和现场",
        "question": "会议室有哪些设备？",
        "answer": "会议室列表中会显示投影、白板、无线投屏、视频会议、音响和直播等设备。需要额外设备时，请在「设备需求」中说明，由管理员确认是否可提供。",
        "keywords": "设备,投影,白板,视频会议,投屏,音响",
    },
    {
        "category": "设备和现场",
        "question": "可以提前到场布置吗？",
        "answer": "请按预约开始时间使用会议室。如确需提前布置，请把所需的开始时间直接写进预约，并在设备需求中说明布置安排。",
        "keywords": "提前到场,布置,彩排,准备",
    },
    {
        "category": "设备和现场",
        "question": "可以带茶歇或外卖吗？",
        "answer": "不同空间规定不同。预约时请在「设备需求」中注明茶歇或餐饮安排，管理员会确认场地限制和清洁要求。",
        "keywords": "茶歇,餐饮,外卖,饮料",
    },
    {
        "category": "设备和现场",
        "question": "会议室支持远程参会吗？",
        "answer": "带有视频会议设备的会议室支持远程参会；大型路演厅还可提供直播支持。请在设备需求中写明平台、连线方式和人流规模。",
        "keywords": "远程,视频会议,线上会议,直播,腾讯会议",
    },
    {
        "category": "账号问题",
        "question": "怎么修改个人信息或登录密码？",
        "answer": "点击右上角头像，选择「个人信息」修改姓名、手机号和邮箱；选择「修改密码」可更新登录密码，修改成功后会自动退出登录。",
        "keywords": "修改密码,个人信息,改资料,账号设置",
    },
    {
        "category": "账号问题",
        "question": "忘记密码了怎么办？",
        "answer": "系统暂不支持自助找回密码，请联系空间管理员，在「会员管理」页面为你重置密码。",
        "keywords": "忘记密码,找回密码,重置密码,密码错误",
    },
    {
        "category": "管理员指南",
        "question": "空间管理员如何审核预约？",
        "answer": "进入「预约审核」页面，可以按状态、空间、开始日期和会员筛选。对待确认预约确认或拒绝并可填写意见；确认时系统会再次校验容量、开放时间和剩余会议室。",
        "keywords": "审核预约,确认预约,拒绝预约,管理员确认",
    },
    {
        "category": "管理员指南",
        "question": "管理员可以维护哪些基础数据？",
        "answer": "管理员可维护空间（城市、地址、开放时段、状态）、会议室（布局、时租价、容量、数量、设备和状态）以及会员账号。已有预约的空间或会议室不可直接删除。",
        "keywords": "管理员,维护,新增空间,新增会议室,会员管理",
    },
    {
        "category": "系统说明",
        "question": "首页看板统计了什么？",
        "answer": "首页展示空间数、会议室规格数、会员数、待确认预约、我的或全部预约数量、今日预约，以及本周空间预约排行和最近预约。普通会员只统计自己的数据。",
        "keywords": "看板,统计,使用率,首页数据",
    },
    {
        "category": "系统说明",
        "question": "智能助手能做什么？",
        "answer": "助手可以查询空间和会议室、检查某时段余量、查看预约、查询规则并生成自然语言预约草稿。只有点击草稿上的「确认预约」后才会写入系统，助手不能绕过容量与时段校验。",
        "keywords": "智能助手,Agent,机器人,自然语言,预约会议",
    },
]


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_schema_updates() -> None:
    """为对话表补充历史操作卡片字段（幂等）。"""
    additions = [
        ("chat_message", "action", "ALTER TABLE chat_message ADD COLUMN action TEXT NULL"),
    ]
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, column, statement in additions:
            columns = {
                item["name"]
                for item in inspector.get_columns(table)
            }
            exists = column in columns
            if not exists:
                connection.execute(text(statement))
                logger.info("已为表 %s 补充字段 %s", table, column)


def seed_data() -> None:
    with SessionLocal() as db:
        if not db.scalar(select(func.count(User.id))):
            db.add_all(
                [
                    User(
                        username=settings.DEFAULT_ADMIN_USERNAME,
                        password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                        name="空间管理员",
                        phone="13800000000",
                        email="admin@meeting-room.local",
                        role="admin",
                        status=1,
                    ),
                    User(
                        username=settings.DEFAULT_USER_USERNAME,
                        password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
                        name="张先生",
                        phone="13900000001",
                        email="member@meeting-room.local",
                        role="user",
                        status=1,
                    ),
                ]
            )
            db.commit()

        if not db.scalar(select(func.count(Venue.id))):
            db.add_all([Venue(**seed) for seed in VENUE_SEEDS])
            db.commit()
            logger.info("已初始化 %s 个会议空间", len(VENUE_SEEDS))

        if not db.scalar(select(func.count(MeetingRoom.id))):
            venue_map = {venue.name: venue.id for venue in db.scalars(select(Venue)).all()}
            db.add_all(
                [
                    MeetingRoom(
                        venue_id=venue_map[venue_name],
                        name=name,
                        code=code,
                        layout=layout,
                        hourly_price=price,
                        capacity=capacity,
                        quantity=quantity,
                        equipment=equipment,
                        status=room_status,
                        description=description,
                    )
                    for (
                        venue_name,
                        name,
                        code,
                        layout,
                        price,
                        capacity,
                        quantity,
                        equipment,
                        room_status,
                        description,
                    ) in MEETING_ROOM_SEEDS
                ]
            )
            db.commit()
            logger.info("已初始化 %s 个会议室规格", len(MEETING_ROOM_SEEDS))

        if not db.scalar(select(func.count(Reservation.id))):
            venue_map = {venue.name: venue.id for venue in db.scalars(select(Venue)).all()}
            room_map = {
                room.name: room for room in db.scalars(select(MeetingRoom)).all()
            }
            member = db.scalar(select(User).where(User.role == "user"))
            admin = db.scalar(select(User).where(User.role == "admin"))
            today = date.today()

            def make_reservation(
                venue_name: str,
                room_name: str,
                start_date: date,
                start_time: time,
                hours: float,
                rooms: int,
                attendees: int,
                status: str,
                remark: str = "",
                equipment: str = "",
            ) -> Reservation:
                room = room_map[room_name]
                start_at = datetime.combine(start_date, start_time)
                end_at = start_at + timedelta(hours=hours)
                return Reservation(
                    venue_id=venue_map[venue_name],
                    meeting_room_id=room.id,
                    user_id=member.id,
                    start_at=start_at,
                    end_at=end_at,
                    hours=hours,
                    rooms=rooms,
                    attendees=attendees,
                    total_amount=float(room.hourly_price) * hours * rooms,
                    equipment_request=equipment,
                    status=status,
                    remark=remark,
                    reviewer_id=admin.id if status in {"confirmed", "rejected"} else None,
                )

            db.add_all(
                [
                    make_reservation(
                        "杭州西湖商务中心",
                        "西湖 A 会议室",
                        today + timedelta(days=1),
                        time(10, 0),
                        2,
                        1,
                        10,
                        "pending",
                        equipment="需要视频会议",
                    ),
                    make_reservation(
                        "上海外滩云舍会议空间",
                        "外滩 1 号",
                        today + timedelta(days=3),
                        time(14, 0),
                        3,
                        1,
                        12,
                        "confirmed",
                        remark="已为您保留会议室并完成设备调试",
                    ),
                    make_reservation(
                        "成都宽窄巷子共享会议室",
                        "宽巷子 1 号",
                        today - timedelta(days=5),
                        time(9, 30),
                        2,
                        1,
                        8,
                        "completed",
                        remark="会议已完成",
                    ),
                    make_reservation(
                        "深圳湾创新中心",
                        "前海路演厅",
                        today + timedelta(days=10),
                        time(13, 0),
                        4,
                        1,
                        80,
                        "rejected",
                        remark="该时段路演厅已有内部活动，建议改期",
                        equipment="需要直播与同传",
                    ),
                ]
            )
            db.commit()
            logger.info("已初始化演示预约数据")

        if not db.scalar(select(func.count(Knowledge.id))):
            db.add_all([Knowledge(**seed) for seed in KNOWLEDGE_SEEDS])
            db.commit()
            logger.info("已初始化 %s 条客服知识库数据", len(KNOWLEDGE_SEEDS))


def init_database() -> None:
    create_tables()
    ensure_schema_updates()
    seed_data()
