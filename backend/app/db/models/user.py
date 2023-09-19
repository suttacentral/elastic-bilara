import datetime
import enum
from enum import Enum
from typing import Optional

from app.db.database import Base
from app.db.models.remark import Remark
from sqlalchemy import Enum as pgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Role(enum.Enum):
    ADMIN = "administrator"
    SUPERUSER = "superuser"
    WRITER = "writer"
    REVIEWER = "reviewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column()
    role: Mapped["Role"] = mapped_column(
        pgEnum(*[role.value for role in Role], name="roles"), nullable=False, default=Role.REVIEWER.value
    )
    created_on: Mapped[datetime.datetime] = mapped_column(nullable=False, default=datetime.datetime.utcnow())
    last_login: Mapped[datetime.datetime] = mapped_column(nullable=False, default=datetime.datetime.utcnow())
    is_active: Mapped[bool] = mapped_column(nullable=False, default=False)

    remarks: Mapped[list["Remark"]] = relationship(back_populates="author")
