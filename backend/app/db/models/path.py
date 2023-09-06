from app.db.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Path(Base):
    __tablename__ = "paths"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(nullable=False, index=True)

    segments: Mapped[list["SegmentUID"]] = relationship(back_populates="segment_path")
