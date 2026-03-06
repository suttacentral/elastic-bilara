"""
DictionaryCache model for caching Pali dictionary lookups.
"""
from datetime import datetime
from typing import Optional

from app.db.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class DictionaryCache(Base):
    """Cache for Pali dictionary API responses."""
    __tablename__ = "dictionary_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    summary_html: Mapped[Optional[str]]
    dpd_html: Mapped[Optional[str]]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
