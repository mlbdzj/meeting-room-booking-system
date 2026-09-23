from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置，可通过 backend/.env 覆盖。"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 数据库
    DATABASE_URL: str = "mysql+pymysql://root:123456@127.0.0.1:3306/meeting_room_booking"

    # 鉴权
    SECRET_KEY: str = "meeting-room-agent-secret-key-please-change"
    TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # 初始化数据
    INIT_DB_ON_STARTUP: bool = True
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "123456"
    DEFAULT_USER_USERNAME: str = "student"
    DEFAULT_USER_PASSWORD: str = "123456"

    # 跨域
    CORS_ORIGINS: str = "*"

    # 智能助手（Agent）
    # auto: 有可用模型则用大模型，否则使用本地知识库引擎；llm: 强制大模型；local: 只用本地引擎
    AGENT_PROVIDER: str = "auto"
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_TIMEOUT: int = 40
    AGENT_MAX_TOOL_ROUNDS: int = 5


settings = Settings()
