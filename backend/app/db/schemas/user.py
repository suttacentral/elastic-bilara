import datetime

from app.db.models.remark import Remark
from app.db.models.user import Role
from pydantic import BaseModel, ConfigDict, EmailStr
from typing_extensions import TypedDict


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    github_id: int
    username: str
    email: EmailStr
    avatar_url: str | None
    role: str = "reviewer"


class UserCreate(UserBase):
    pass


class User(UserBase):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    id: int
    created_on: datetime.datetime
    last_login: datetime.datetime
    is_active: bool


class UserUpdatePayload(TypedDict, total=False):
    is_active: bool
    username: str
    email: EmailStr
    avatar_url: str | None
    role: Role
    created_on: datetime.datetime
    last_login: datetime.datetime
