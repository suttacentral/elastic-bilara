from typing import Annotated

from app.services.auth import utils
from app.services.projects.models import ProjectsOut
from app.services.users.schema import UserData
from fastapi import APIRouter, Depends
from search.search import Search

router = APIRouter(prefix="/projects")

search = Search()


@router.get("/", response_model=ProjectsOut)
async def get_projects(
    user: Annotated[UserData, Depends(utils.get_current_user)],
    prefix: str | None = None,
) -> ProjectsOut:
    return ProjectsOut(projects=search.find_unique_data(field="muid", prefix=prefix))
