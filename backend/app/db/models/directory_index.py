from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DirectoryIndexState(Base):
    __tablename__ = "directory_index_state"

    work_directory: Mapped[str] = mapped_column(Text, primary_key=True)
    ready: Mapped[bool] = mapped_column(default=False)


class DirectoryIndexEntry(Base):
    __tablename__ = "directory_index_entries"

    work_directory: Mapped[str] = mapped_column(Text, primary_key=True)
    path: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    search_name: Mapped[str] = mapped_column(Text)
