import datetime

from app.db.database import Base
from app.db.models.segment_uid import SegmentUID
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Remark(Base):
    __tablename__ = "remarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(nullable=False)
    segment_uid_id: Mapped[int] = mapped_column(ForeignKey("segment_uids.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False, default=datetime.datetime.utcnow())

    author: Mapped["User"] = relationship(back_populates="remarks")
    segment_uid: Mapped["SegmentUID"] = relationship(back_populates="remarks")
