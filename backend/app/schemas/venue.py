from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class VenueIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    city: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=160)
    rating: int = Field(default=4, ge=1, le=5)
    room_count: int = Field(default=1, ge=1, le=5000)
    open_time: str = Field(default="09:00", pattern=TIME_PATTERN)
    close_time: str = Field(default="18:00", pattern=TIME_PATTERN)
    status: int = 1
    description: str = ""

    @model_validator(mode="after")
    def check_hours(self):
        if self.close_time <= self.open_time:
            raise ValueError("关闭时间必须晚于开放时间")
        return self


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    city: str
    address: str
    rating: int
    room_count: int
    open_time: str
    close_time: str
    status: int
    description: str
    created_at: datetime | None = None
    meeting_room_count: int = 0
    reservation_count: int = 0

    @model_validator(mode="after")
    def check_hours(self):
        if self.close_time <= self.open_time:
            raise ValueError("关闭时间必须晚于开放时间")
        return self
