from pydantic import BaseModel


class ProjectsOut(BaseModel):
    projects: list[str]


class RootPathsOut(BaseModel):
    root_paths: list[str]


class JSONDataOut(BaseModel):
    can_edit: bool
    data: dict[str, str]
