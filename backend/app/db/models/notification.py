from datetime import datetime

from app.db.database import Base
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(nullable=False, index=True)
    commit_id: Mapped[str] = mapped_column(nullable=False, index=True)


class RemarkNotification(Base):
    __tablename__ = "remark_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recipient_github_id: Mapped[int] = mapped_column(nullable=False, index=True)
    actor_username: Mapped[str] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(nullable=False)
    uid: Mapped[str] = mapped_column(nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(nullable=False, index=True)
    source_file_path: Mapped[str] = mapped_column(nullable=False)
    remark_value: Mapped[str | None] = mapped_column(nullable=True)
    is_done: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        index=True,
    )
