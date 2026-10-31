"""pytest 公共夹具：默认使用内存 SQLite，不依赖 MySQL 与外网。"""

import os
from types import SimpleNamespace

os.environ.setdefault("INIT_DB_ON_STARTUP", "false")
os.environ.setdefault("AGENT_PROVIDER", "local")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models import Knowledge, MeetingRoom, User, Venue

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
TEST_PASSWORD = "123456"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


@pytest.fixture(scope="session")
def engine():
    if TEST_DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seed(db):
    """最小演示数据：2 个空间、4 个会议室规格、3 个账号、1 条知识库。"""
    admin = User(
        username="admin",
        password_hash=TEST_PASSWORD_HASH,
        name="空间管理员",
        role="admin",
        status=1,
    )
    member = User(
        username="student",
        password_hash=TEST_PASSWORD_HASH,
        name="张先生",
        phone="13800000000",
        role="user",
        status=1,
    )
    stranger = User(
        username="lisi",
        password_hash=TEST_PASSWORD_HASH,
        name="李四",
        role="user",
        status=1,
    )
    db.add_all([admin, member, stranger])
    db.flush()

    venue = Venue(
        name="杭州西湖商务中心",
        city="杭州",
        address="西湖区文三路 88 号",
        rating=5,
        room_count=12,
        open_time="08:30",
        close_time="20:00",
        status=1,
    )
    closed_venue = Venue(
        name="旧空间",
        city="杭州",
        address="测试路 9 号",
        rating=3,
        room_count=6,
        open_time="09:00",
        close_time="18:00",
        status=0,
    )
    db.add_all([venue, closed_venue])
    db.flush()

    boardroom = MeetingRoom(
        venue_id=venue.id,
        name="西湖 A 会议室",
        code="MR-HZ-001",
        layout="课桌式",
        hourly_price=120,
        capacity=10,
        quantity=3,
        equipment="投影、白板、视频会议",
        status="open",
    )
    small = MeetingRoom(
        venue_id=venue.id,
        name="西湖 B 会议室",
        code="MR-HZ-002",
        layout="U 型",
        hourly_price=180,
        capacity=2,
        quantity=1,
        equipment="双屏、无线投屏",
        status="open",
    )
    maintenance = MeetingRoom(
        venue_id=venue.id,
        name="维护中路演厅",
        code="MR-HZ-003",
        layout="剧院式",
        hourly_price=260,
        capacity=30,
        quantity=2,
        equipment="LED 屏",
        status="maintenance",
    )
    closed_room = MeetingRoom(
        venue_id=closed_venue.id,
        name="旧空间会议室",
        code="MR-HZ-004",
        layout="圆桌式",
        hourly_price=100,
        capacity=6,
        quantity=2,
        equipment="白板",
        status="open",
    )
    db.add_all([boardroom, small, maintenance, closed_room])
    db.add(
        Knowledge(
            category="预约规则",
            question="会议空间开放时间是几点？",
            answer="杭州西湖商务中心开放时间为 08:30-20:00，具体以空间详情为准。",
            keywords="开放时间,营业时间,几点,什么时候",
            status=1,
        )
    )
    db.flush()

    return SimpleNamespace(
        admin=admin,
        member=member,
        stranger=stranger,
        venue=venue,
        closed_venue=closed_venue,
        boardroom=boardroom,
        small=small,
        maintenance=maintenance,
        closed_room=closed_room,
    )


@pytest.fixture
def admin_headers(seed):
    from helpers import auth_headers

    return auth_headers(seed.admin)


@pytest.fixture
def member_headers(seed):
    from helpers import auth_headers

    return auth_headers(seed.member)


@pytest.fixture
def stranger_headers(seed):
    from helpers import auth_headers

    return auth_headers(seed.stranger)
