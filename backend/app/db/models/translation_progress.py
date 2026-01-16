import datetime

from app.db.database import Base
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class TranslationProgress(Base):
    """Database model for caching translation progress data"""
    __tablename__ = "translation_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(128), index=True)
    muid: Mapped[str] = mapped_column(String(128), index=True)
    progress: Mapped[float] = mapped_column(default=0.0)
    total_keys: Mapped[int] = mapped_column(default=0)
    translated_keys: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow
    )
