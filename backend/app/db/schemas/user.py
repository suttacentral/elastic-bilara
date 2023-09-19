import datetime

from app.db.models.remark import Remark
from pydantic import BaseModel, ConfigDict, EmailStr


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

    remarks: list[Remark]
