import datetime

from app.db.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(nullable=False)
    commit_id: Mapped[str] = mapped_column(nullable=False)
