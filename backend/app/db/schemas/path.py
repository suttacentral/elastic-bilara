from app.db.models.segment_uid import SegmentUID
from pydantic import BaseModel, ConfigDict


class PathBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    path: str


class PathCreate(PathBase):
    pass


class Path(PathBase):
    id: int

    segments: list[SegmentUID]
