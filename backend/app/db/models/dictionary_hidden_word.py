from app.db.database import Base
from sqlalchemy import UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


class DictionaryHiddenWord(Base):
    __tablename__ = "dictionary_hidden_words"
    __table_args__ = (
        UniqueConstraint("word", "github_id", name="uq_hidden_word_github_id"),
        Index("idx_hidden_words_word", "word"),
        Index("idx_hidden_words_github_id", "github_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(nullable=False)
    github_id: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
