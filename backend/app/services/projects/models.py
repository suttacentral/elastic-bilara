from pydantic import BaseModel


class ProjectsOut(BaseModel):
    projects: list[str]


class PathsOut(BaseModel):
    paths: list[str]


class JSONDataOut(BaseModel):
    can_edit: bool
    data: dict[str, str]
    task_id: str | None = None
