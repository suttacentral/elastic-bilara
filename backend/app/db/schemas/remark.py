import re
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.services.projects.utils import search, sort_paths
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class RemarkBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    remark_value: Optional[str]
    source_file_path: Optional[Path] = None
    segment_id: str
    muid: Optional[str] = None
    prefix: Optional[str] = None

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

    @model_validator(mode="before")
    @classmethod
    def source_file_path_based_on_muid_prefix_validator(cls, data: Any):
        if isinstance(data, dict):
            muid = data.get("muid")
            prefix = data.get("prefix")
            source_file_path = data.get("source_file_path")
        elif issubclass(RemarkBase, cls):
            muid = cls.muid
            prefix = cls.prefix
            source_file_path = cls.source_file_path
        else:
            muid = None
            prefix = None
            source_file_path = None
        if source_file_path:
            return data
        if not source_file_path and muid and prefix:
            paths = sort_paths(search.get_file_paths(muid=muid, _type="file_path", prefix=prefix))
            if not paths:
                raise ValueError(f"Path not found for muid: {muid} and prefix: {prefix}")
            if isinstance(data, dict):
                data["source_file_path"] = Path(paths[0])
            elif issubclass(RemarkBase, cls):
                cls.source_file_path = Path(paths[0])
        return data


class Remark(RemarkBase):
    id: int
