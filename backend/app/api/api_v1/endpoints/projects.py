from pathlib import Path
from typing import Annotated

from app.core.config import settings
from app.db.schemas.user import User, UserBase
from app.services.auth import utils
from app.services.directories.utils import (
    create_directory,
    create_file,
    get_language,
    validate_path,
    validate_root_data,
    get_matches,
)
from app.services.projects.models import (
    JSONDataOut,
    PathsOut,
    ProjectsOut,
    MergeIn,
    SplitIn,
    MergeOut,
    SplitOut,
    CalleeMerge,
    Affected,
)
from app.services.projects.uid_reducer import UIDReducer
from app.services.projects.utils import (
    OverrideException,
    create_new_project_file_names,
    create_project_file,
    sort_paths,
    update_file,
    write_json_data,
)
from app.services.users.permissions import (
    can_create_projects,
    can_delete_projects,
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
from search.utils import (
    find_root_path,
    get_filename,
    get_json_data,
    get_muid,
    get_prefix,
)

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


@router.patch(
    "/merge/",
    response_model=MergeOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
async def merge_segments(user: Annotated[UserBase, Depends(utils.get_current_user)], payload: MergeIn):
    file_path = Path(
        list(search.get_file_paths(muid=payload.muid, prefix=payload.prefix, exact=True, _type="file_path"))[0]
    )
    affected_paths_data_before = {}
    related = get_matches(file_path, True)
    for path in related:
        data = get_json_data(path)
        if path == file_path:
            callee_data_before = data
        else:
            affected_paths_data_before[path] = data
        data[payload.merger_uid] = data[payload.merger_uid] + " " + data[payload.mergee_uid]
        write_json_data(path, data)

    reducer = UIDReducer(user, file_path, [payload.mergee_uid])
    main_task_id, related_task_id = reducer.decrement()

    affected_paths_data_after = {}
    for path in related:
        if path == file_path:
            callee_data_after = get_json_data(path)
        else:
            affected_paths_data_after[path] = get_json_data(path)

    callee = CalleeMerge(
        prefix=payload.prefix,
        muid=payload.muid,
        data_before=callee_data_before,
        data_after=callee_data_after,
        merger={"uid": payload.merger_uid, "value": callee_data_before[payload.merger_uid]},
        mergee={"uid": payload.mergee_uid, "value": callee_data_before[payload.mergee_uid]},
    )

    affected = [
        Affected(
            muid=get_muid(path),
            source_muid=get_muid(find_root_path(path)),
            language=get_language(path),
            filename=get_filename(path),
            prefix=get_prefix(path),
            path=str(path).replace(str(settings.WORK_DIR), ""),
            data_after=affected_paths_data_after[path],
            data_before=affected_paths_data_before[path],
        )
        for path in related
        if path != file_path
    ]

    return MergeOut(
        main_task_id=main_task_id,
        related_task_id=related_task_id,
        message="Segments merged successfully!",
        path=str(file_path).replace(str(settings.WORK_DIR), ""),
        callee=callee,
        affected=affected,
    )


@router.patch(
    "/split/",
    response_model=SplitOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
async def split_segments(user: Annotated[UserBase, Depends(utils.get_current_user)], payload: SplitIn):
    pass


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


@router.get("/{path:path}/source/")
async def get_source_muid(user: Annotated[UserBase, Depends(utils.get_current_user)], path: Path):
    target_path = validate_path(str(path))
    source = find_root_path(target_path)
    return {"muid": get_muid(source), "path": str(source).replace(str(settings.WORK_DIR), "")}


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
    if root_path.parts[0] == "root":
        root_path = settings.WORK_DIR.joinpath(root_path)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Path '{root_path}' not starting in 'root/' directory.",
        )
    if not root_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Root path '{root_path}' not found",
        )
    if root_path.is_dir() and not list(root_path.glob("*.json")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Root path directory '{root_path}' contains no json files."
            f" Target directory must contain at least one json file.",
        )

    directory_list = ["translation", "comment"]

    new_project_paths = create_new_project_file_names(
        source_user.username, translation_language, root_path, directory_list
    )
    source_root_files_names: list[Path] = list(
        root_path.glob("*.json") if root_path.is_dir() else root_path.parent.glob("*.json")
    )

    all_paths_list: list[Path] = []
    for root_file, new_file_path in zip(source_root_files_names, new_project_paths):
        for directory_type_path in new_file_path:
            if create_project_file(Path(root_file), Path(directory_type_path)):
                all_paths_list.append(directory_type_path)
    if not all_paths_list:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No new project files were created",
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
        "new_project_paths": [path.relative_to(settings.WORK_DIR) for path in all_paths_list],
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


@router.patch("/{path:path}/")
async def delete_segment_ids(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    data: list[str],
    path: Path = Depends(validate_path),
    exact: bool = False,
    dry_run: bool = False,
):
    if not can_delete_projects(int(user.github_id)):
        raise HTTPException(status_code=403, detail="You are not allowed to change projects")
    uid_reducer = UIDReducer(user, Path(path), uids=data, exact=exact)
    if dry_run:
        data = uid_reducer.decrement_dry()
        results = []
        for path in data:
            results.append(
                {
                    "muid": get_muid(Path(path)),
                    "source_muid": get_muid(find_root_path(Path(path))),
                    "language": get_language(Path(path)),
                    "filename": get_filename(Path(path)),
                    "prefix": get_prefix(Path(path)),
                    "path": str(path).replace(str(settings.WORK_DIR), ""),
                    "data_after": data[path],
                    "data_before": get_json_data(path),
                }
            )
        paths = {str(res["path"]) for res in results}
        results.sort(
            key=lambda x: (
                not x["muid"].startswith("root"),
                x["muid"],
                x["prefix"],
                sort_paths(paths).index(x["path"]),
            )
        )
        return JSONResponse(status_code=200, content={"message": "Dry run successful", "results": results})
    main_path_task_id, related_paths_task_id = uid_reducer.decrement()
    return JSONResponse(
        status_code=200,
        content={
            "message": "Segment IDs deleted successfully",
            "main_task_id": main_path_task_id,
            "related_task_id": related_paths_task_id,
        },
    )
