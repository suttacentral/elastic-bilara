import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException


from app.core.config import settings
from app.core.text_types import TextType
from app.db.schemas.user import UserBase
from app.services.directories.finder import Finder
from app.services.projects.utils import write_json_data
from app.services.users.utils import get_user
from search.search import Search
from search.utils import get_prefix, get_muid
from app.tasks import commit

es = Search()


def validate_path(path: str):
    target_path: Path = settings.WORK_DIR / path
    if not target_path.exists() or not target_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Path {path} not found")
    if str(target_path.relative_to(settings.WORK_DIR)).split("/")[0] not in {item.value for item in TextType}:
        raise HTTPException(status_code=400, detail=f"Path {path} not allowed")
    return target_path


def validate_root_data(path: Path, data: dict[str, str]):
    if not data:
        raise HTTPException(status_code=400, detail=f"Data is empty")
    if not all(is_prefix_in_uid(get_prefix(path), uid) for uid in list(data.keys())):
        raise HTTPException(status_code=400, detail=f"Prefix and segment ID do not match")
    return data


def create_directory(path: Path) -> bool:
    if not can_create_root_dir(path):
        return False
    matches = get_matches(path)
    [dir_path.mkdir(parents=True, exist_ok=True) for dir_path in matches]
    return True


def create_and_write(user: UserBase, paths: list[Path], data: dict[str, str], message: str, retries: int = 10):
    for path in paths:
        path.touch()
        _, file_error = write_json_data(path, data)
        if file_error:
            raise HTTPException(status_code=500, detail=f"Error writing to file")
        created: bool = False
        error_counter: int = 0
        while not created:
            created, _ = es.add_to_index(path)
            error_counter += 1
            if error_counter > retries:
                path.unlink()
                raise HTTPException(status_code=500, detail=f"Error adding to elastic, file deleted")
    commit.delay(get_user(int(user.github_id)).model_dump(), [str(path) for path in paths], message)
    return True


def create_file(user: UserBase, path: Path, data: dict[str, str]):
    if not can_create_root_text(path):
        return False
    full_path = settings.WORK_DIR / path
    create_and_write(user, [full_path], data, f"{user.username} created new root file {path}")
    matches = get_matches(path)
    related_paths: list[Path] = [replace_muids(settings.WORK_DIR / match / path.parts[-1]) for match in matches]
    related_paths.remove(full_path)
    create_and_write(
        user,
        [path for path in related_paths if not path.exists()],
        {key: "" for key in data.keys()},
        f"{user.username} created related files to the {path}",
    )
    return True


def is_prefix_in_uid(prefix: str, uid: str) -> bool:
    if "-" in prefix:
        parts = prefix.split(".", 1)
        start, end = map(int, re.findall(r"\d+", parts[1]))
        for i in range(start, end + 1):
            full_prefix = f"{parts[0]}.{i}"
            m = re.match(rf"^{full_prefix}(\D|$)", uid)
            if m:
                return True
    return uid.startswith(prefix)


def can_create_root_dir(path: Path) -> bool:
    if path.parts[0].lower() != TextType.ROOT.value:
        return False
    if dir_exists(path):
        return False
    return True


def can_create_root_text(path: Path) -> bool:
    text_type: str = path.parts[0]
    if text_type.lower() != TextType.ROOT.value:
        return False
    if path.suffix != ".json":
        return False
    if not dir_exists(path):
        return False
    query: dict[str, Any] = {
        "bool": {
            "must": [
                {"term": {"prefix": {"value": get_prefix(path)}}},
                {"term": {"is_root": {"value": True}}},
            ]
        }
    }
    if es.is_in_index(query=query) or (settings.WORK_DIR / path).exists():
        return False
    return get_muid_from_name(path) == get_muid_from_path(path)


def dir_exists(path: Path) -> bool:
    path: Path = settings.WORK_DIR / path
    if not is_valid_directory(path.parts[len(settings.WORK_DIR.parts)]):
        return False
    if not path.exists() and not path.name.endswith(".json"):
        return False
    for parent in path.parents:
        if not parent.exists():
            return False
    return True


def get_muid_from_path(path: Path) -> str:
    return "-".join(path.parts[:3]).replace("-blurb", "")


def get_muid_from_name(path: Path) -> str:
    return path.stem.split("_")[1]


def is_valid_directory(text_type: str) -> bool:
    return any(text_type == e.value for e in TextType)


def replace_muids(path: Path) -> Path:
    return Path(str(path).replace(path.stem.split("_")[-1], get_muid(path).replace("-blurb", "")))


def get_matches(target_path: Path) -> set[Path]:
    finder = Finder()
    return finder.find(target_path)
