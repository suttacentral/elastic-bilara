import json
import re
from pathlib import Path
from typing import Annotated

from app.core.config import settings
from app.db.schemas.user import UserBase
from app.services.auth import utils
from app.services.users.permissions import is_admin_or_superuser, is_user_active
from fastapi import APIRouter, Depends, HTTPException, status
from search.search import Search
from search.utils import find_root_path, get_json_data, get_prefix, yield_file_path

router = APIRouter(prefix="/tags")

TAGS_FILE = settings.WORK_DIR / "_tags.json"

TAG_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

search = Search()


def _read_tags() -> list[dict]:
    if not TAGS_FILE.exists():
        return []
    with open(TAGS_FILE, "r") as f:
        return json.load(f)


def _write_tags(tags: list[dict]) -> None:
    with open(TAGS_FILE, "w") as f:
        json.dump(tags, f, indent=2, ensure_ascii=False)


def _validate_tag_name(tag_name: str) -> None:
    if not TAG_NAME_PATTERN.match(tag_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tag name '{tag_name}'. Must be lowercase alphanumeric with hyphens only.",
        )


@router.get("/")
async def get_tags(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
) -> list[dict]:
    return _read_tags()


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
async def create_tag(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    data: dict,
) -> dict:
    tag_name = data.get("tag", "").strip()
    if not tag_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag name is required")
    _validate_tag_name(tag_name)

    tags = _read_tags()
    if any(t["tag"] == tag_name for t in tags):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Tag '{tag_name}' already exists")

    new_tag = {
        "tag": tag_name,
        "expansion": data.get("expansion", ""),
        "definition": data.get("definition", ""),
    }
    tags.append(new_tag)
    _write_tags(tags)
    return new_tag


@router.patch(
    "/{tag_name}/",
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
async def update_tag(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    tag_name: str,
    data: dict,
) -> dict:
    tags = _read_tags()
    for tag in tags:
        if tag["tag"] == tag_name:
            if "expansion" in data:
                tag["expansion"] = data["expansion"]
            if "definition" in data:
                tag["definition"] = data["definition"]
            if "tag" in data and data["tag"] != tag_name:
                new_name = data["tag"].strip()
                _validate_tag_name(new_name)
                if any(t["tag"] == new_name for t in tags if t is not tag):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Tag '{new_name}' already exists",
                    )
                tag["tag"] = new_name
            _write_tags(tags)
            return tag
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tag '{tag_name}' not found")


@router.delete(
    "/{tag_name}/",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
async def delete_tag(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    tag_name: str,
) -> dict:
    tags = _read_tags()
    original_len = len(tags)
    tags = [t for t in tags if t["tag"] != tag_name]
    if len(tags) == original_len:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tag '{tag_name}' not found")
    _write_tags(tags)
    return {"detail": f"Tag '{tag_name}' deleted"}


@router.post(
    "/data/{prefix}/",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
async def create_tag_data_file(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    prefix: str,
) -> dict:
    """Create a new tag data file for a given prefix, mirroring the root file structure."""
    # Check if tag file already exists on disk
    tag_dir = settings.WORK_DIR / "tag"
    if tag_dir.exists():
        for f in yield_file_path(tag_dir, level=1):
            if get_prefix(f) == prefix:
                # File exists — ensure it's indexed and return
                search.add_to_index(f)
                return {"detail": f"Tag data file for '{prefix}' already exists", "path": str(f)}

    # Find root file to get segment keys and directory structure
    root_files: set[str] = search.get_file_paths(muid="root-pli-ms", prefix=prefix, exact=True, _type="file_path")
    if not root_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Root file for prefix '{prefix}' not found",
        )
    root_path = Path(root_files.pop())
    root_data = get_json_data(root_path)

    # Build tag file path mirroring root directory structure
    # root: root/pli/ms/sutta/sn/sn1/sn1.1_root-pli-ms.json
    # tag:  tag/pli/ms/sutta/sn/sn1/sn1.1_tag.json
    relative_parts = root_path.relative_to(settings.WORK_DIR / "root").parts
    # relative_parts = ('pli', 'ms', 'sutta', 'sn', 'sn1', 'sn1.1_root-pli-ms.json')
    tag_filename = f"{prefix}_tag.json"
    tag_file_path = settings.WORK_DIR / "tag" / Path(*relative_parts[:-1]) / tag_filename

    # Create directory and file
    tag_file_path.parent.mkdir(parents=True, exist_ok=True)
    tag_data = {key: "" for key in root_data.keys()}
    with open(tag_file_path, "w") as f:
        json.dump(tag_data, f, indent=2, ensure_ascii=False)

    # Index in ES
    search.add_to_index(tag_file_path)

    return {"detail": f"Tag data file created for '{prefix}'", "path": str(tag_file_path)}


@router.post(
    "/reindex/",
    dependencies=[Depends(is_admin_or_superuser), Depends(is_user_active)],
)
async def reindex_tag_files(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
) -> dict:
    """Scan all tag files on disk and index any that are not yet in ES."""
    tag_dir = settings.WORK_DIR / "tag"
    if not tag_dir.exists():
        return {"detail": "No tag directory found", "indexed": 0}

    indexed_count = 0
    for f in yield_file_path(tag_dir, level=1):
        success, error = search.add_to_index(f)
        if success:
            indexed_count += 1

    return {"detail": f"Reindexed {indexed_count} tag file(s)", "indexed": indexed_count}
