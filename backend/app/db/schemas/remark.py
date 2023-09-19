import datetime

from app.db.models.segment_uid import SegmentUID
from app.db.models.user import User
from pydantic import BaseModel, ConfigDict


class RemarkBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    value: str
    segment_uid_id: int
    author_id: int


class RemarkCreate(RemarkBase):
    pass


class Remark(RemarkBase):
    id: int
    created_at: datetime.datetime

    author: User
    segment_uid: SegmentUID
