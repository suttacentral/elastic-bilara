from app.db.database import Base
from app.db.models.path import Path
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship


class SegmentUID(Base):
    __tablename__ = "segment_uids"

    id: Mapped[int] = mapped_column(primary_key=True)
    segment_uid: Mapped[str] = mapped_column(nullable=False, index=True)
    segment_path_id: Mapped[int] = mapped_column(ForeignKey("paths.id"), index=True)

    segment_path: Mapped["Path"] = relationship(back_populates="segments")
    remarks: Mapped[list["Remark"]] = relationship(back_populates="segment_uid")
