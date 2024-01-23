from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.text_types import TextType
from app.db.schemas.user import UserBase
from app.services.directories.models import FilesAndDirsOut
from app.services.directories import utils
from app.services.auth.utils import get_current_user
from app.services.directories.remover import Remover
from app.services.directories.utils import get_muid_from_path, get_language
from app.services.projects.utils import sort_paths
from app.services.users.permissions import can_delete_projects

router = APIRouter(prefix="/directories")


@router.get("/", response_model=FilesAndDirsOut)
async def get_root_content(user: Annotated[UserBase, Depends(get_current_user)]):
    directories = []
    for p in settings.WORK_DIR.iterdir():
        if p.is_dir() and p.name in {item.value for item in TextType}:
            directories.append(str(p.relative_to(settings.WORK_DIR)) + "/")
    return FilesAndDirsOut(directories=directories)


@router.get("/{path:path}/", response_model=FilesAndDirsOut)
async def get_dir_content(
    user: Annotated[UserBase, Depends(get_current_user)], target_path: Path = Depends(utils.validate_dir_path)
):
    base = str(target_path.relative_to(settings.WORK_DIR)) + "/"
    directories = []
    files = []

    for p in target_path.iterdir():
        if p.is_dir() and p.name not in {item.value for item in TextType}:
            dir_path = str(p.relative_to(settings.WORK_DIR)) + "/"
            directories.append(dir_path.replace(base, "", 1))
        elif p.is_file() and str(target_path) != str(settings.WORK_DIR):
            file_path = str(p.relative_to(settings.WORK_DIR))
            files.append(file_path.replace(base, "", 1))

    return FilesAndDirsOut(base=base, directories=directories, files=files)


@router.delete("/{path:path}/")
async def delete_path(
    user: Annotated[UserBase, Depends(get_current_user)],
    target_path: Path = Depends(utils.validate_path),
    dry_run: bool = False,
):
    if not can_delete_projects(int(user.github_id)):
        raise HTTPException(status_code=403, detail="You are not allowed to delete projects")
    remover = Remover(user, target_path)
    if dry_run:
        data = remover.delete_dry()
        results = []
        for path in data:
            results.append(
                {
                    "muid": get_muid_from_path(Path(str(path).removeprefix("/"))),
                    "language": get_language(Path(path)),
                    "is_parent": Path(path).parts[-1] == target_path.parts[-1],
                    "path": path,
                }
            )
        results.sort(
            key=lambda x: (
                not x["muid"].startswith("root"),
                x["muid"],
                not x["is_parent"],
                sort_paths(set(data)).index(x["path"]),
            )
        )
        return JSONResponse(status_code=200, content={"message": "Dry run successful", "results": results})
    main_path_task_id, related_paths_task_id = remover.delete()
    return JSONResponse(
        status_code=200,
        content={
            "message": "Deletion successful",
            "main_task_id": main_path_task_id,
            "related_paths_task_id": related_paths_task_id,
        },
    )
