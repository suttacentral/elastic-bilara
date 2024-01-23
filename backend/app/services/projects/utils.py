import json
import re
from pathlib import Path

from app.core.text_types import TextType
from app.db.schemas.user import UserBase
from app.services.git import utils
from app.services.users.utils import get_user
from app.tasks import commit
from search.search import Search
from search.utils import get_json_data, find_root_path

search = Search()


def sort_paths(paths: set[str]) -> list[str]:
    def extract_key(s):
        head = s.rsplit("/", 1)[-1]
        head_parts = re.split(r"(\d+)", head)
        return [int(part) if part.isdigit() else part for part in head_parts]

    return sorted(paths, key=extract_key)


def update_file(
    path: Path, data: dict[str, str], root_path: Path, user: UserBase
) -> tuple[bool, Exception | None, str | None]:
    user: UserBase = get_user(int(user.github_id))
    root_data: dict[str, str] = get_json_data(root_path)
    task_id = None

    for key in data:
        if key not in root_data:
            return False, KeyError(f"{key} not found in the root file"), task_id

    file_data: dict[str, str] = get_json_data(path)

    original_data: dict[str, str] = file_data.copy()

    for key, value in data.items():
        file_data[key] = value

    updated, elastic_error = search.update_segments(path, file_data)

    if elastic_error:
        return False, elastic_error, task_id

    written, file_error = write_json_data(path, file_data)
    cleaned_path_string = str(utils.clean_path(str(path)))
    if written:
        result = commit.delay(user.model_dump(), str(path), f"Translations by {user.username} to {cleaned_path_string}")
        task_id = result.id

    if file_error:
        updated = False
        while not updated:
            updated, _ = search.update_segments(path, original_data)
        return False, file_error, task_id

    return True, None, task_id


def write_json_data(path: Path, data: dict[str, str]) -> tuple[bool, Exception | None]:
    try:
        with open(path, "w") as f:
            json.dump(sort_data(data, path), f, indent=2, ensure_ascii=False)
    except (OSError, TypeError) as e:
        return False, e
    return True, None


def sort_data(data: dict[str, str], path: Path):
    if TextType.ROOT.value in path.parts:
        return data
    root_path = find_root_path(path)
    if root_path:
        root_data = get_json_data(root_path)
        return {uid: data[uid] for uid in root_data if uid in data}
