from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserBase(BaseModel):
    name: str = Field(default="", max_length=50)
    phone: str = Field(default="", max_length=20)
    email: str = Field(default="", max_length=100)


class RegisterIn(UserBase):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=50)
    confirm_password: str = Field(min_length=6, max_length=50)

    @field_validator("username")
    @classmethod
    def check_username(cls, value: str) -> str:
        value = value.strip()
        if not value.replace("_", "").isalnum():
            raise ValueError("账号只能包含字母、数字和下划线")
        return value

    @field_validator("confirm_password")
    @classmethod
    def check_password(cls, value: str, info):
        if info.data.get("password") and value != info.data["password"]:
            raise ValueError("两次输入的密码不一致")
        return value


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=50)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    status: int
    created_at: datetime | None = None


class LoginOut(BaseModel):
    token: str
    user: UserOut


class UserCreate(UserBase):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=50)
    role: str = "user"
    status: int = 1

    @field_validator("role")
    @classmethod
    def check_role(cls, value: str) -> str:
        if value not in {"admin", "user"}:
            raise ValueError("角色只能是 admin 或 user")
        return value


class UserUpdate(UserBase):
    role: str = "user"
    status: int = 1


class PasswordUpdate(BaseModel):
    old_password: str | None = None
    new_password: str = Field(min_length=6, max_length=50)


class ProfileUpdate(UserBase):
    pass
