from typing import Optional

from app.db.database import Base
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(
        unique=True, nullable=False, index=True
    )
    notification_authors: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    notification_days: Mapped[Optional[int]] = mapped_column(nullable=True)
    pali_lookup: Mapped[Optional[bool]] = mapped_column(
        nullable=True, default=True
    )
    dblclick_search: Mapped[Optional[bool]] = mapped_column(
        nullable=True, default=True
    )
