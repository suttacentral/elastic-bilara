from pathlib import Path
from typing import Annotated

from app.core.config import settings
from app.db.schemas.user import User, UserBase
from app.services.auth import utils
from app.services.directories.utils import (
    create_directory,
    create_file,
    validate_root_data,
)
from app.services.projects.models import JSONDataOut, PathsOut, ProjectsOut
from app.services.projects.utils import (
    OverrideException,
    create_new_project_file_names,
    create_project_file,
    sort_paths,
    update_file,
)
from app.services.users.permissions import (
    can_create_projects,
    can_edit_translation,
    is_admin_or_superuser,
    is_user_active,
    is_user_in_admin_group,
)
from app.services.users.utils import get_user
from app.tasks import commit
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from search.search import Search
from search.utils import get_json_data

router = APIRouter(prefix="/projects")

search = Search()


@router.get("/", response_model=ProjectsOut)
async def get_projects(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    prefix: str | None = None,
) -> ProjectsOut:
    projects = search.find_unique_data(field="muid", prefix=prefix)
    if not projects:
        projects = search.get_distinct_data(field="muid", prefix=prefix)
    return ProjectsOut(projects=projects)


@router.get("/{muid}/", response_model=PathsOut)
async def get_paths_for_project(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    muid: str,
    prefix: str | None = None,
    _type: Annotated[str, Query(enum=["root_path", "file_path"], min_length=9, max_length=9)] = "root_path",
) -> PathsOut:
    data: list[str] = sort_paths(search.get_file_paths(muid=muid, _type=_type, prefix=prefix))
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{muid}' not found")
    return PathsOut(paths=data)


@router.get("/{muid}/can-edit/", response_model=dict[str, bool])
async def get_can_edit(user: Annotated[UserBase, Depends(utils.get_current_user)], muid: str) -> dict[str, bool]:
    return {"can_edit": can_edit_translation(int(user.github_id), muid)}


@router.get("/{muid}/{prefix}/", response_model=JSONDataOut)
async def get_json_data_for_prefix_in_project(
    user: Annotated[UserBase, Depends(utils.get_current_user)], muid: str, prefix: str
) -> JSONDataOut:
    file: set[str] = search.get_file_paths(muid=muid, prefix=prefix, exact=True, _type="file_path")
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data for project '{muid}' and prefix '{prefix}' not found",
        )
    can_edit: bool = can_edit_translation(int(user.github_id), muid)
    data: dict[str, str] = get_json_data(Path(file.pop()))
    return JSONDataOut(can_edit=can_edit, data=data)


@router.patch("/{muid}/{prefix}/", response_model=JSONDataOut)
async def update_json_data_for_prefix_in_project(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    muid: str,
    prefix: str,
    data: dict[str, str],
) -> JSONDataOut:
    if not can_edit_translation(int(user.github_id), muid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit this resource")
    file: set[str] = search.get_file_paths(muid=muid, prefix=prefix, exact=True, _type="file_path")
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data for project '{muid}' and prefix '{prefix}' not found",
        )
    path: Path = Path(file.pop())
    root_path: set[str] = search.get_file_paths(muid=muid, prefix=prefix, exact=True)
    updated, error, task_id = update_file(path, data, Path(root_path.pop()), user)
    if error:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if isinstance(error, KeyError):
            code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(error).strip("'"))
    return JSONDataOut(can_edit=True, data=data, task_id=task_id)


@router.post(
    "/create/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
async def create_new_project(
    current_user: Annotated[UserBase, Depends(utils.get_current_user)],
    user_github_id: int,
    root_path: Path,
    translation_language: str,
):
    try:
        current_user = get_user(current_user.github_id)
        source_user = get_user(user_github_id)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_github_id} not found. {e}")
    if not root_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Root path '{root_path}' not found",
        )
    directory_list = ["translation", "comment"]

    new_project_paths = create_new_project_file_names(
        source_user.username, translation_language, root_path, directory_list
    )
    source_root_files_names: list[Path] = list(
        root_path.glob("*.json") if root_path.is_dir() else root_path.parent.glob("*.json")
    )

    all_paths_list: list[Path] = []
    try:
        for root_file, new_file_path in zip(source_root_files_names, new_project_paths):
            for directory_type_path in new_file_path:
                create_project_file(Path(root_file), Path(directory_type_path))
                all_paths_list.append(directory_type_path)
    except OverrideException as e:
        for path in all_paths_list:
            path.unlink()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"rolling_back": f"{all_paths_list}", "error": str(e)},
        )
    search.update_indexes(settings.ES_INDEX, settings.ES_SEGMENTS_INDEX, all_paths_list)
    result = commit.delay(
        current_user.model_dump(),
        [str(path) for path in all_paths_list],
        f"Creating new project for {source_user.username} in {translation_language.upper()} language",
    )

    return {
        "user": source_user.username,
        "translation_language": translation_language,
        "new_project_paths": new_project_paths,
        "commit_task_id": result.id,
    }


@router.post("/{path:path}/")
async def create_project(
    user: Annotated[UserBase, Depends(utils.get_current_user)], path: str, data: dict[str, str] | None = None
):
    if not can_create_projects(int(user.github_id)):
        raise HTTPException(status_code=403, detail="You are not allowed to create projects")
    if not data and not path.endswith(".json"):
        if not create_directory(Path(path)):
            raise HTTPException(status_code=400, detail=f"Directory {path} and related were not created")
        return JSONResponse(status_code=201, content={"detail": f"Directory {path} and related have been created"})
    if data and path.endswith(".json"):
        validate_root_data(Path(path), data)
        if not create_file(user, Path(path), data):
            raise HTTPException(status_code=400, detail=f"File {path} and related were not created")
        return JSONResponse(status_code=201, content={"detail": f"File {path} and related have been created"})
    raise HTTPException(status_code=400, detail=f"Path {path} and related were not created")
