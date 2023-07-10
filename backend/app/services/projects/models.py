from pydantic import BaseModel


class ProjectsOut(BaseModel):
    projects: list[str]
