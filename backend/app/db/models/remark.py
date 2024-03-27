from app.db.database import Base
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Remark(Base):
    __tablename__ = "remarks"
    __table_args__ = (UniqueConstraint("source_file_path", "segment_id", name="source_file_path_segment_id_constrain"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    remark_value: Mapped[str] = mapped_column(nullable=True)
    source_file_path: Mapped[str] = mapped_column(nullable=False)
    segment_id: Mapped[str] = mapped_column(nullable=False)
