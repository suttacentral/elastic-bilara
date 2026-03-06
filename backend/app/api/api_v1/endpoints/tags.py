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


def _find_all_tag_files() -> list[Path]:
    """Find all tag files in the tag directory."""
    tag_dir = settings.WORK_DIR / "tag"
    if not tag_dir.exists():
        return []

    result = []
    for f in yield_file_path(tag_dir, level=1):
        if f.name.endswith("_tag.json"):
            result.append(Path(f))
    return result


def _parse_tag_value(value: str) -> list[str]:
    """Parse comma-separated tag value, preserving leading spaces.

    Example: "practice, 4nt" -> ["practice", " 4nt"]
    """
    if not value or not value.strip():
        return []
    return value.split(",")


def _serialize_tag_value(tags: list[str]) -> str:
    """Serialize tag list back to comma-separated string.

    Example: ["practice", " 4nt"] -> "practice, 4nt"
    """
    return ",".join(tags)


def _delete_tag_from_files(tag_name: str) -> int:
    """Remove a tag from all tag files. Returns the number of files modified."""
    tag_files = _find_all_tag_files()
    modified_count = 0

    for tag_file in tag_files:
        try:
            with open(tag_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            changed = False
            for segment_key in data:
                tag_value = data[segment_key]
                if not tag_value or not tag_value.strip():
                    continue

                # Parse the tag value
                tags = _parse_tag_value(tag_value)
                # Filter out tag_name (comparing stripped versions)
                filtered_tags = [t for t in tags if t.strip() != tag_name]

                if len(filtered_tags) != len(tags):
                    # A tag was removed
                    data[segment_key] = _serialize_tag_value(filtered_tags)
                    changed = True

            if changed:
                with open(tag_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                modified_count += 1
        except Exception as e:
            # Continue with other files on error
            continue

    return modified_count


def _update_tag_in_files(old_tag_name: str, new_tag_name: str) -> int:
    """Rename a tag in all tag files. Returns the number of files modified."""
    tag_files = _find_all_tag_files()
    modified_count = 0

    for tag_file in tag_files:
        try:
            with open(tag_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            changed = False
            for segment_key in data:
                tag_value = data[segment_key]
                if not tag_value or not tag_value.strip():
                    continue

                # Parse the tag value
                tags = _parse_tag_value(tag_value)
                # Replace old_tag_name with new_tag_name
                new_tags = []
                segment_changed = False
                for t in tags:
                    if t.strip() == old_tag_name:
                        # Replace with new name, preserving the leading spaces
                        leading_spaces = len(t) - len(t.lstrip())
                        new_tags.append(" " * leading_spaces + new_tag_name)
                        segment_changed = True
                    else:
                        new_tags.append(t)

                if segment_changed:
                    data[segment_key] = _serialize_tag_value(new_tags)
                    changed = True

            if changed:
                with open(tag_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                modified_count += 1
        except Exception as e:
            # Continue with other files on error
            continue

    return modified_count


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
                # Update tag name in all tag files before updating the definition
                files_modified = _update_tag_in_files(tag_name, new_name)
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

    # Delete tag from all tag files before removing from definitions
    files_modified = _delete_tag_from_files(tag_name)

    _write_tags(tags)
    return {
        "detail": f"Tag '{tag_name}' deleted",
        "files_modified": files_modified,
    }


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
