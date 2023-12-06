from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.text_types import TextType
from app.db.schemas.user import UserBase
from app.services.directories.models import FilesAndDirsOut
from app.services.directories import utils
from app.services.auth.utils import get_current_user

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
    user: Annotated[UserBase, Depends(get_current_user)], target_path: Path = Depends(utils.validate_path)
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
