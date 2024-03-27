import re
from pathlib import Path
from typing import Optional

from app.core.config import settings
from pydantic import BaseModel, ConfigDict, FilePath, field_validator


class RemarkBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    remark_value: Optional[str]
    source_file_path: Path
    segment_id: str

    @field_validator("segment_id")
    @classmethod
    def segment_id_validator(cls, value: str):
        if re.search(r"^(([\w]+[\w\d.-]*\d)+\:(\d+\.)+\d)$", value) is None:
            raise ValueError('segment_id does not meet required format e.g. "dn1.1:0.1.1"')
        return value

    @field_validator("source_file_path")
    @classmethod
    def source_file_path_validator(cls, value: Path | str):
        if isinstance(value, str):
            value = Path(value)
        if not value.is_relative_to(settings.WORK_DIR):
            value = settings.WORK_DIR.joinpath(value)
        if not value.is_file():
            raise ValueError(f"File {value} does not exist")
        return str(value)


class Remark(RemarkBase):
    id: int
