from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectsOut(BaseModel):
    projects: list[str]


class PathsOut(BaseModel):
    paths: list[str]


class JSONDataOut(BaseModel):
    can_edit: bool
    data: dict[str, str]
    task_id: str | None = None
    materialized: bool = True
    structure_revision: str | None = None


class StructurePreviewIn(BaseModel):
    muid: str
    prefix: str
    operation: Literal['split', 'merge']
    uid: str


class StructureCommitIn(StructurePreviewIn):
    operation_id: UUID
    revision: str
    edits: dict[str, dict[str, str]] = Field(default_factory=dict)
    reviewed: list[str] = Field(default_factory=list)


class StructureStatusIn(BaseModel):
    muid: str
    prefix: str
    operation_id: UUID


class HtmlValidationIn(BaseModel):
    overrides: dict[str, str] = Field(default_factory=dict)
    segments: dict[str, str] | None = None


class HtmlValidationIssueOut(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    uid: str
    offset: int
    message: str
    related_uid: str | None = None


class HtmlValidationOut(BaseModel):
    valid: bool
    checked_segments: int
    errors: list[HtmlValidationIssueOut] = Field(default_factory=list)
    warnings: list[HtmlValidationIssueOut] = Field(default_factory=list)
