from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReservationIn(BaseModel):
    venue_id: int = Field(ge=1)
    meeting_room_id: int = Field(ge=1)
    start_at: datetime
    end_at: datetime
    rooms: int = Field(default=1, ge=1, le=20)
    attendees: int = Field(default=1, ge=1, le=100)
    contact_phone: str = Field(default="", max_length=20)
    equipment_request: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_at <= self.start_at:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class ReservationReview(BaseModel):
    action: str = Field(pattern="^(confirm|reject)$")
    remark: str = Field(default="", max_length=255)


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int
    venue_name: str = ""
    meeting_room_id: int
    meeting_room_name: str = ""
    user_id: int
    username: str = ""
    user_name: str = ""
    start_at: datetime
    end_at: datetime
    hours: float
    rooms: int
    attendees: int
    contact_phone: str = ""
    total_amount: float = 0
    equipment_request: str = ""
    status: str
    status_text: str = ""
    remark: str = ""
    reviewer_name: str = ""
    reviewed_at: datetime | None = None
    ended_at: datetime | None = None
    ended_early: bool = False
    created_at: datetime | None = None


class StatOverview(BaseModel):
    venue_total: int
    meeting_room_total: int
    user_total: int
    reservation_total: int
    pending_total: int
    today_reservation_total: int
    utilization_rate: int
    week_total: int
    week_start: date
    week_end: date
    venue_ranking: list[dict]
    recent_reservations: list[ReservationOut]
