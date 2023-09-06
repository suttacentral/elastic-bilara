from app.db.models.path import Path
from app.db.models.remark import Remark
from pydantic import BaseModel, ConfigDict


class SegmentUIDBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    segment_uid: str
    segment_path_id: int


class SegmentUIDCreate(SegmentUIDBase):
    pass


class SegmentUID(SegmentUIDBase):
    id: int

    segment_path: Path
    remarks: list[Remark]
