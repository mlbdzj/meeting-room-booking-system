from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MEETING_ROOM_STATUS = {"open", "maintenance", "closed"}


class MeetingRoomIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    code: str = Field(default="", max_length=50)
    layout: str = Field(default="", max_length=40)
    venue_id: int = Field(ge=1)
    hourly_price: float = Field(default=0, ge=0, le=999999)
    capacity: int = Field(default=2, ge=1, le=500)
    quantity: int = Field(default=1, ge=1, le=999)
    equipment: str = Field(default="", max_length=500)
    status: str = "open"
    description: str = ""

    @field_validator("status")
    @classmethod
    def check_status(cls, value: str) -> str:
        if value not in MEETING_ROOM_STATUS:
            raise ValueError("会议室状态不合法")
        return value


class MeetingRoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    layout: str
    venue_id: int
    venue_name: str = ""
    hourly_price: float
    capacity: int
    quantity: int
    equipment: str
    status: str
    description: str
    created_at: datetime | None = None
