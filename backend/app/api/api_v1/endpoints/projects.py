from pathlib import Path
from typing import Annotated

from app.services.auth import utils
from app.services.projects.models import JSONDataOut, ProjectsOut, RootPathsOut
from app.services.projects.utils import sort_paths
from app.services.users.permissions import can_edit_translation
from app.services.users.schema import UserData
from fastapi import APIRouter, Depends, HTTPException, status
from search.search import Search
from search.utils import get_json_data

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
    data: list[str] = sort_paths(search.get_file_paths(muid=muid))
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{muid}' not found")
    return RootPathsOut(root_paths=data)


@router.get("/{muid}/{prefix}/", response_model=JSONDataOut)
async def get_json_data_for_prefix_in_project(
    user: Annotated[UserData, Depends(utils.get_current_user)], muid: str, prefix: str
) -> JSONDataOut:
    file: set[str] = search.get_file_paths(muid=muid, prefix=prefix, _type="file_path")
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data for project '{muid}' and prefix '{prefix}' not found",
        )
    can_edit: bool = can_edit_translation(int(user.github_id), muid)
    data: dict[str, str] = get_json_data(Path(file.pop()))
    return JSONDataOut(can_edit=can_edit, data=data)
