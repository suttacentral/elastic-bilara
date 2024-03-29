import re
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, model_validator

from search.search import Search
from search.utils import get_json_data

search = Search()


class ProjectsOut(BaseModel):
    projects: list[str]


class PathsOut(BaseModel):
    paths: list[str]


class JSONDataOut(BaseModel):
    can_edit: bool
    data: dict[str, str]
    task_id: str | None = None


def validate_exists(v: str, field: Any) -> str:
    data = search.find_unique_data(field=field.name)
    if not data:
        data = search.get_distinct_data(field=field.name)
    if v not in data:
        raise ValueError(f"'{field.name}' '{v}' not found in projects")
    return v


class MergeSplitInBase(BaseModel):
    prefix: Annotated[str, validate_exists]
    muid: Annotated[str, validate_exists]
    _uids_to_validate: list[str] = []

    @model_validator(mode="after")
    def validate_prefix_belongs_in_muid(self) -> "MergeSplitInBase":
        data = search.get_file_paths(muid=self.muid, prefix=self.prefix, exact=True, _type="file_path")
        if not data:
            raise ValueError(f"prefix '{self.prefix}' does not belong to muid '{self.muid}'")
        return self

    @model_validator(mode="after")
    def validate_uids_in_project(self) -> "MergeSplitInBase":
        uids = search.get_uids(prefix=self.prefix, muid=self.muid)
        for uid_name in self._uids_to_validate:
            uid = getattr(self, uid_name)
            if uid not in uids:
                raise ValueError(f"{uid_name} '{uid}' not found in project '{self.muid}' with prefix '{self.prefix}'")
        return self

    @model_validator(mode="after")
    def validate_uids_format(self) -> "MergeSplitInBase":
        for uid_name in self._uids_to_validate:
            uid = getattr(self, uid_name)
            if not re.search(r"(\d+(\.\d+)+)$", uid):
                raise ValueError(f"{uid_name} '{uid}' has a wrong format")
        return self


class MergeIn(MergeSplitInBase):
    merger_uid: str
    mergee_uid: str
    _uids_to_validate: list[str] = ["merger_uid", "mergee_uid"]

    @model_validator(mode="after")
    def validate_uids_order(self) -> "MergeSplitInBase":
        file_path = Path(
            list(search.get_file_paths(muid=self.muid, prefix=self.prefix, exact=True, _type="file_path"))[0]
        )
        uids = list(get_json_data(file_path).keys())
        uids_to_check = [getattr(self, uid_name) for uid_name in self._uids_to_validate]
        if uids.index(uids_to_check[1]) - uids.index(uids_to_check[0]) != 1:
            raise ValueError(f"UIDs '{uids_to_check[0]}' and '{uids_to_check[1]}' are not right after each other")
        return self


class SplitIn(MergeSplitInBase):
    splitter_uid: str
    _uids_to_validate: list[str] = ["splitter_uid"]


class Affected(BaseModel):
    muid: str
    source_muid: str
    language: str
    filename: str
    prefix: str
    path: str
    data_after: dict[str, str]
    data_before: dict[str, str]


class CalleeBase(BaseModel):
    prefix: str
    muid: str
    data_after: dict[str, str]
    data_before: dict[str, str]


class CalleeMerge(CalleeBase):
    merger: dict[str, str]
    mergee: dict[str, str]


class CalleeSplit(CalleeBase):
    splitter: dict[str, str]


class MergeSplitOutBase(BaseModel):
    main_task_id: str
    related_task_id: str
    message: str
    path: str
    callee: CalleeBase
    affected: list[Affected]


class MergeOut(MergeSplitOutBase):
    callee: CalleeMerge


class SplitOut(MergeSplitOutBase):
    callee: CalleeSplit
