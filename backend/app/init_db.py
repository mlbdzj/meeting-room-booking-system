"""初始化数据库表结构与演示数据。"""

import logging
from datetime import date, timedelta

from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import Reservation, Venue, Knowledge, MeetingRoom, User

logger = logging.getLogger("meeting-room-agent")


VENUE_SEEDS = [
    {
        "name": "杭州西湖智选假日会议空间",
        "city": "杭州",
        "address": "西湖区文三路 88 号",
        "star": 5,
        "room_count": 180,
        "open_time": "14:00",
        "close_time": "12:00",
        "description": "步行 10 分钟可达西湖景区，含自助早餐与健身房，适合商务与亲子出行。",
    },
    {
        "name": "上海外滩云舍会议空间",
        "city": "上海",
        "address": "黄浦区中山东一路 12 号",
        "star": 4,
        "room_count": 120,
        "open_time": "15:00",
        "close_time": "12:00",
        "description": "坐落外滩核心地段，会议室可观浦江夜景，配备行政酒廊与会议厅。",
    },
    {
        "name": "成都宽窄巷子花园会议空间",
        "city": "成都",
        "address": "青羊区长顺上街 66 号",
        "star": 4,
        "room_count": 96,
        "open_time": "14:00",
        "close_time": "12:00",
        "description": "紧邻宽窄巷子，庭院式设计，提供川式早餐与茶室。",
    },
    {
        "name": "三亚亚龙湾海景度假会议空间",
        "city": "三亚",
        "address": "亚龙湾国家旅游度假区",
        "star": 5,
        "room_count": 260,
        "open_time": "15:00",
        "close_time": "12:00",
        "description": "私属沙滩与无边泳池，含亲子俱乐部与海景餐厅，适合度假长住。",
    },
]

# (会议空间名, 会议室类型名, 编号, 床型, 价格/晚, 可住人数, 会议室余量, 状态, 描述)
MEETING_ROOM_SEEDS = [
    ("杭州西湖智选假日会议空间", "高级大床房", "RT-HZ-001", "1.8m 大床", 458, 2, 40, "open", "含双早，可免费使用健身房。"),
    ("杭州西湖智选假日会议空间", "高级双床房", "RT-HZ-002", "1.2m 双床", 498, 2, 35, "open", "适合双人同住，房间面积 32㎡。"),
    ("杭州西湖智选假日会议空间", "湖景套房", "RT-HZ-003", "1.8m 大床", 988, 3, 12, "open", "独立客厅，可加床，含行政酒廊礼遇。"),
    ("上海外滩云舍会议空间", "城市景观大床房", "RT-SH-001", "1.8m 大床", 688, 2, 30, "open", "高层城市景观，28㎡，含双早。"),
    ("上海外滩云舍会议空间", "江景双床房", "RT-SH-002", "1.2m 双床", 788, 2, 24, "open", "可看浦江夜景，含双早。"),
    ("上海外滩云舍会议空间", "外滩套房", "RT-SH-003", "1.8m 大床", 1688, 3, 8, "maintenance", "套房维护中，暂不接受预约。"),
    ("成都宽窄巷子花园会议空间", "花园大床房", "RT-CD-001", "1.8m 大床", 398, 2, 28, "open", "庭院景观，含川式早餐。"),
    ("成都宽窄巷子花园会议空间", "家庭房", "RT-CD-002", "1.5m 双床 + 加床", 568, 4, 16, "open", "适合一家四口，含四早。"),
    ("三亚亚龙湾海景度假会议空间", "海景大床房", "RT-SY-001", "1.8m 大床", 1088, 2, 60, "open", "正面海景，含双早与沙滩服务。"),
    ("三亚亚龙湾海景度假会议空间", "海景双床房", "RT-SY-002", "1.35m 双床", 1188, 2, 50, "open", "海景阳台，含双早。"),
    ("三亚亚龙湾海景度假会议空间", "泳池别墅", "RT-SY-003", "2m 大床", 2888, 4, 10, "closed", "别墅已停售，等待翻新。"),
]

KNOWLEDGE_SEEDS = [
    {
        "category": "预约流程",
        "question": "怎么预约会议空间房间？",
        "answer": "进入「会议空间管理」页面选择空间，点击「立即预约」，在弹窗中选择使用开始日期、使用结束日期、会议室类型与间数，填写使用开始人数和特殊要求后点击「提交预约」。提交后状态为「待确认」，会议空间确认后预约生效。也可以直接告诉智能助手，例如「帮我订下周五使用开始两晚的杭州西湖智选假日会议空间大床房，2 个人」。",
        "keywords": "预约,怎么订,订房,下单,订会议空间",
    },
    {
        "category": "预约流程",
        "question": "在哪里查看我的预约？",
        "answer": "点击左侧「我的预约」，可以按状态筛选查看全部预约，包含会议空间、会议室类型、使用开始使用结束日期、晚数、间数、总价与确认意见；待确认或已确认的预约可以在这里直接取消。",
        "keywords": "我的预约,预约记录,查看预约,预约状态",
    },
    {
        "category": "预约流程",
        "question": "使用开始和使用结束时间是什么时候？",
        "answer": "使用开始时间通常为 14:00 之后，使用结束时间为次日 12:00 之前；部分空间（如上海外滩云舍会议空间、三亚亚龙湾海景度假会议空间）使用开始时间为 15:00。具体以预约卡片和会议空间详情中的说明为准，如需提前使用开始或延迟使用结束可联系前台。",
        "keywords": "使用开始时间,使用结束时间,几点使用开始,几点使用结束",
    },
    {
        "category": "预约流程",
        "question": "预约提交后多久会被确认？",
        "answer": "系统没有自动确认，需要会议空间工作人员在「预约确认」页面处理。通常在提交后当天完成确认，建议至少提前 1 天预约；临近使用开始的预约会优先处理。",
        "keywords": "多久确认,确认时间,什么时候确认",
    },
    {
        "category": "预约流程",
        "question": "怎么取消预约？",
        "answer": "在「我的预约」页面找到状态为「待确认」或「已确认」的预约，点击「取消预约」并确认即可；也可以让智能助手帮你取消。已拒绝、已取消、已完成的预约无法再操作。",
        "keywords": "取消预约,退订,取消预约,不去了",
    },
    {
        "category": "预约流程",
        "question": "预约被拒绝了怎么办？",
        "answer": "在「我的预约」页面的「确认意见」列可以看到拒绝原因（例如会议室余量不足、特殊要求无法满足）。根据原因调整日期、会议室类型或间数后重新下单即可；如有疑问可联系会议空间前台。",
        "keywords": "拒绝,被拒,预约被拒,确认意见",
    },
    {
        "category": "会议室类型与会议室余量",
        "question": "会议室类型的会议室余量和剩余会议室余量怎么看？",
        "answer": "每个会议室类型都有固定会议室余量（库存间数）。在会议空间详情与预约弹窗中，可以看到所选日期内的剩余会议室余量；系统按下单日期的区间统计占用间数，剩余会议室余量不足时无法下单，避免超卖。",
        "keywords": "会议室余量,剩余房,库存,还有房吗,满房",
    },
    {
        "category": "会议室类型与会议室余量",
        "question": "一间房可以住几个人？",
        "answer": "以会议室类型的「可住人数」为准：常见大床房/双床房可住 2 人，家庭房可住 4 人，套房可住 3 人。使用开始人数不能超过「可住人数 × 间数」，人数较多时建议加订房间。",
        "keywords": "几个人,能住几人,加人,超员",
    },
    {
        "category": "会议室类型与会议室余量",
        "question": "房价是怎么计算的？",
        "answer": "总价 = 会议室类型单价（每晚）× 使用开始晚数 × 间数。下单时系统会自动计算并在预约卡片上显示总价，例如 458 元/晚的高级大床房，住 2 晚 1 间，总价为 916 元。",
        "keywords": "价格,房价,多少钱,总价,计算",
    },
    {
        "category": "会议室类型与会议室余量",
        "question": "可以加床吗？",
        "answer": "部分会议室类型支持加床（例如杭州西湖智选假日会议空间的湖景套房），加床会占用可住人数上限，并可能产生额外费用。下单时请在「特殊要求」中注明「需要加床」，由会议空间确认后生效。",
        "keywords": "加床,加人,婴儿床",
    },
    {
        "category": "支付与发票",
        "question": "需要先付押金吗？",
        "answer": "系统当前只做预约登记，不在线收款。到店后按会议空间规定支付房费与押金，使用结束时押金原路退还；企业协议客户可走月结，具体联系前台。",
        "keywords": "押金,付款,支付,到店付",
    },
    {
        "category": "支付与发票",
        "question": "可以开发票吗？",
        "answer": "可以。使用结束时在前台提供开票信息（单位名称、税号）即可开具增值税普通发票或专用发票；需要提前开票的请在预约「特殊要求」中注明，由会议空间协助处理。",
        "keywords": "发票,开票,报销,税号",
    },
    {
        "category": "使用开始须知",
        "question": "可以带宠物使用开始吗？",
        "answer": "除三亚亚龙湾海景度假会议空间的部分会议室类型外，多数空间暂不接待宠物。若需携带宠物，请先联系会议空间前台确认会议室类型与清洁费标准，并在预约特殊要求中注明。",
        "keywords": "宠物,带狗,带猫,宠物友好",
    },
    {
        "category": "使用开始须知",
        "question": "使用开始需要带什么证件？",
        "answer": "使用开始时需出示本人有效身份证件（身份证/护照），一人一证；未携带证件无法办理使用开始。如需增加同住人，请在预约特殊要求中提前说明。",
        "keywords": "证件,身份证,登记,使用开始材料",
    },
    {
        "category": "使用开始须知",
        "question": "可以提前使用开始或延迟使用结束吗？",
        "answer": "视当日会议室状态而定。提前使用开始可能需要加收费用，延迟使用结束超过 18:00 通常按全天房费计算。请在预约特殊要求中注明，或提前联系会议空间前台确认。",
        "keywords": "提前使用开始,延迟使用结束,加时,晚点使用结束",
    },
    {
        "category": "账号问题",
        "question": "怎么修改个人信息或登录密码？",
        "answer": "点击右上角头像，选择「个人信息」可以修改姓名、手机号和邮箱；选择「修改密码」可以修改登录密码，需要先输入原密码，修改成功后系统会自动退出登录。",
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
        "question": "空间管理员如何确认预约？",
        "answer": "管理员登录后进入「预约确认」页面，可按状态、会议空间、使用开始日期和会员筛选预约。对待确认的预约点击「确认」或「拒绝」，可填写确认意见；确认时系统会再次校验该会议室类型的剩余会议室余量，避免超卖。",
        "keywords": "确认预约,预约确认,管理员确认,拒绝预约",
    },
    {
        "category": "管理员指南",
        "question": "管理员可以维护哪些基础数据？",
        "answer": "管理员可以维护三类数据：1）「会议空间管理」新增、编辑、删除空间（城市、地址、星级、会议室数、使用开始使用结束时间、营业状态）；2）「会议室类型管理」维护会议室类型（床型、价格、可住人数、会议室余量、状态）；3）「会员管理」新增会员、修改角色与状态、重置密码。删除会议空间前需先删除其会议室类型，存在预约的会议空间或会议室类型不能删除。",
        "keywords": "管理员,维护,新增会议空间,新增会议室类型,会员管理",
    },
    {
        "category": "系统说明",
        "question": "首页看板统计了什么？",
        "answer": "首页展示空间数、会议室类型数、会员数（仅管理员）、待确认预约、今日使用开始预约、今日使用开始率，以及按本周使用开始预约数排名的空间排行和最近预约。普通用户看到的预约统计仅包含自己的预约。",
        "keywords": "看板,统计,使用开始率,首页数据,多少条",
    },
]


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_schema_updates() -> None:
    """为已存在的旧表补充后续新增的字段（幂等，可重复执行）。"""
    additions = [
        ("chat_message", "action", "ALTER TABLE chat_message ADD COLUMN action TEXT NULL"),
    ]
    with engine.begin() as connection:
        for table, column, statement in additions:
            exists = connection.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() AND table_name = :table AND column_name = :column"
                ),
                {"table": table, "column": column},
            ).scalar()
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
                        email="admin@venue.local",
                        role="admin",
                        status=1,
                    ),
                    User(
                        username=settings.DEFAULT_USER_USERNAME,
                        password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
                        name="张先生",
                        phone="13900000001",
                        email="guest@venue.local",
                        role="user",
                        status=1,
                    ),
                ]
            )
            db.commit()
            logger.info("已初始化默认账号：%s / %s", settings.DEFAULT_ADMIN_USERNAME, settings.DEFAULT_USER_USERNAME)

        if not db.scalar(select(func.count(Venue.id))):
            db.add_all([Venue(**seed) for seed in VENUE_SEEDS])
            db.commit()
            logger.info("已初始化 %s 家会议空间", len(VENUE_SEEDS))

        if not db.scalar(select(func.count(MeetingRoom.id))):
            venue_map = {venue.name: venue.id for venue in db.scalars(select(Venue)).all()}
            db.add_all(
                [
                    MeetingRoom(
                        venue_id=venue_map[venue_name],
                        name=name,
                        code=code,
                        layout=layout,
                        price=price,
                        capacity=capacity,
                        quantity=quantity,
                        status=room_status,
                        description=description,
                    )
                    for venue_name, name, code, layout, price, capacity, quantity, room_status, description in MEETING_ROOM_SEEDS
                ]
            )
            db.commit()
            logger.info("已初始化 %s 个会议室类型", len(MEETING_ROOM_SEEDS))

        if not db.scalar(select(func.count(Reservation.id))):
            venue_map = {venue.name: venue.id for venue in db.scalars(select(Venue)).all()}
            room_map = {room.name: room for room in db.scalars(select(MeetingRoom)).all()}
            guest = db.scalar(select(User).where(User.role == "user"))
            admin = db.scalar(select(User).where(User.role == "admin"))
            today = date.today()

            def make_reservation(venue_name, room_name, check_in, hours, rooms, attendees, status, remark="", special=""):
                room = room_map[room_name]
                return Reservation(
                    venue_id=venue_map[venue_name],
                    meeting_room_id=room.id,
                    user_id=guest.id,
                    start_at=check_in,
                    end_at=check_in + timedelta(days=hours),
                    hours=hours,
                    rooms=rooms,
                    attendees=attendees,
                    total_amount=float(room.price) * hours * rooms,
                    equipment_request=special,
                    status=status,
                    remark=remark,
                    reviewer_id=admin.id if status in {"confirmed", "rejected"} else None,
                )

            db.add_all(
                [
                    make_reservation("杭州西湖智选假日会议空间", "高级大床房", today + timedelta(days=1), 2, 1, 2, "pending", special="希望安排安静楼层"),
                    make_reservation("上海外滩云舍会议空间", "江景双床房", today + timedelta(days=3), 1, 1, 2, "confirmed", remark="已为您保留江景房，祝使用开始愉快"),
                    make_reservation("成都宽窄巷子花园会议空间", "花园大床房", today - timedelta(days=5), 2, 1, 2, "completed", remark="已完成使用开始"),
                    make_reservation("三亚亚龙湾海景度假会议空间", "海景双床房", today + timedelta(days=10), 3, 2, 4, "rejected", remark="该日期房源紧张，建议改期", special="需要两间相邻房间"),
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
