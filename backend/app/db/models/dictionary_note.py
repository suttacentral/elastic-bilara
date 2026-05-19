from app.db.database import Base
from sqlalchemy import UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


class DictionaryNote(Base):
    __tablename__ = "dictionary_notes"
    __table_args__ = (
        UniqueConstraint("word", "github_id", name="uq_word_github_id"),
        Index("idx_dictionary_notes_word", "word"),
        Index("idx_dictionary_notes_github_id", "github_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(nullable=False)
    note_value: Mapped[str] = mapped_column(nullable=False)
    github_id: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
