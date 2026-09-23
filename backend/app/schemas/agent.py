import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeIn(BaseModel):
    category: str = Field(default="常见问题", max_length=50)
    question: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1)
    keywords: str = Field(default="", max_length=255)
    status: int = 1


class KnowledgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    question: str
    answer: str
    keywords: str
    status: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: int | None = None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    source: str = ""
    tools: str = ""
    action: dict | None = None
    created_at: datetime | None = None

    @field_validator("action", mode="before")
    @classmethod
    def parse_action(cls, value):
        if isinstance(value, str):
            if not value.strip():
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value


class ChatReply(BaseModel):
    session_id: int
    reply: ChatMessageOut
    suggestions: list[str] = Field(default_factory=list)
    provider: str = "local"
    action: dict | None = None


class ChatActionIn(BaseModel):
    """确认 / 取消聊天中的待办操作（按消息定位，草稿以服务端存储为准）。"""

    session_id: int
    message_id: int


class ChatActionOut(BaseModel):
    action: dict
    message: ChatMessageOut
    reservation: dict | None = None


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AgentStatus(BaseModel):
    provider: str
    model: str = ""
    llm_enabled: bool
    knowledge_total: int
    tools: list[str] = Field(default_factory=list)
