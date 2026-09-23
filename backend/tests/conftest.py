"""pytest 公共夹具：默认跑在内存 SQLite 上，不依赖 MySQL 与外网。

三个刻意的隔离设计：

- ``INIT_DB_ON_STARTUP=false``：导入应用时不会连开发库、不会写入演示数据；
- ``AGENT_PROVIDER=local``：助手强制走本地知识库引擎，测试不调用外部大模型，结果可复现；
- 每个用例跑在自己的事务里并在结束时回滚，用例之间互不影响。

如需对着真实 MySQL 跑，设置环境变量 ``TEST_DATABASE_URL`` 指向一个测试库即可
（例如 ``mysql+pymysql://root:123456@127.0.0.1:3306/meeting_room_booking_test``）；
夹具会自动建表与清理，请不要指向开发库。
"""

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
from app.models import Venue, Knowledge, MeetingRoom, User

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
TEST_PASSWORD = "123456"
# PBKDF2 迭代 12 万次，只算一次，避免每个用例重复计算
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
    """把会话绑在一条外层事务上，用例内部的 commit 只落在外层事务里。"""
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
    """最小演示数据：2 家会议空间、4 个会议室类型、3 个账号、1 条知识库。"""
    admin = User(
        username="admin", password_hash=TEST_PASSWORD_HASH, name="空间管理员", role="admin", status=1
    )
    member = User(
        username="student", password_hash=TEST_PASSWORD_HASH, name="张先生", role="user", status=1
    )
    stranger = User(
        username="lisi", password_hash=TEST_PASSWORD_HASH, name="李四", role="user", status=1
    )
    db.add_all([admin, member, stranger])
    db.flush()

    venue = Venue(
        name="杭州西湖智选假日会议空间", city="杭州", address="西湖区北山街 1 号", star=5, room_count=30, status=1
    )
    closed_venue = Venue(name="停业会议空间", city="杭州", address="测试路 9 号", star=3, room_count=6, status=0)
    db.add_all([venue, closed_venue])
    db.flush()

    king = MeetingRoom(
        venue_id=venue.id, name="高级大床房", layout="大床", price=458, capacity=2, quantity=3, status="open"
    )
    twin = MeetingRoom(
        venue_id=venue.id, name="双床房", layout="双床", price=528, capacity=2, quantity=1, status="open"
    )
    maintenance = MeetingRoom(
        venue_id=venue.id, name="维护中套房", layout="大床", price=888, capacity=2, quantity=2, status="maintenance"
    )
    closed_room = MeetingRoom(
        venue_id=closed_venue.id, name="停业会议室类型", layout="大床", price=300, capacity=2, quantity=2, status="open"
    )
    db.add_all([king, twin, maintenance, closed_room])
    db.add(
        Knowledge(
            category="使用开始须知",
            question="使用开始和使用结束时间是几点？",
            answer="使用开始时间为 14:00 之后，使用结束时间为次日 12:00 之前。",
            keywords="使用开始时间,使用结束时间,几点,什么时候",
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
        king=king,
        twin=twin,
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
