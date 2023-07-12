from typing import Annotated

from app.services.auth import utils
from app.services.projects.models import ProjectsOut, RootPathsOut
from app.services.projects.utils import sort_paths
from app.services.users.schema import UserData
from fastapi import APIRouter, Depends, HTTPException, status
from search.search import Search

router = APIRouter(prefix="/projects")

search = Search()


@router.get("/", response_model=ProjectsOut)
async def get_projects(
    user: Annotated[UserData, Depends(utils.get_current_user)],
    prefix: str | None = None,
) -> ProjectsOut:
    return ProjectsOut(projects=search.find_unique_data(field="muid", prefix=prefix))


@router.get("/{muid}/", response_model=RootPathsOut)
async def get_root_paths_for_project(
    user: Annotated[UserData, Depends(utils.get_current_user)], muid: str
) -> RootPathsOut:
    data = sort_paths(search.get_file_paths(muid=muid))
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{muid}' not found")
    return RootPathsOut(root_paths=data)
