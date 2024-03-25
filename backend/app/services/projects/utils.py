import json
import re
from pathlib import Path

from app.core.config import settings
from app.core.text_types import TextType
from app.db.schemas.user import User, UserBase
from app.services.git import utils
from app.services.users.utils import get_user
from app.tasks import commit
from search.search import Search
from search.utils import find_root_path, get_json_data

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


def create_new_project_paths(
    username: str, translation_language: str, root_path: Path, directory_list: list[str]
) -> list[Path]:
    if "root" not in root_path.parts:
        raise ValueError(f"Path {root_path} does not contain 'root' directory")

    root_dir_path = (
        Path().joinpath(*root_path.parts[root_path.parts.index("root") + 3 :])  # client's naming convention logic
        if root_path.is_dir()
        else Path().joinpath(*root_path.parts[root_path.parts.index("root") + 3 :]).parent
    )
    return [
        settings.WORK_DIR.joinpath(directory, translation_language.lower(), username.lower(), root_dir_path)
        for directory in directory_list
    ]


def generate_file_name_prefixes(root_path: Path) -> list[str]:
    root_path = root_path.parent if root_path.suffix == ".json" else root_path
    return [file_path.name.split("_")[0] for file_path in root_path.iterdir()]


def create_new_project_file_names(
    username: str, translation_language_code: str, root_path: Path, directory_list: list[str]
) -> list[tuple[Path, ...]]:
    new_project_paths = create_new_project_paths(username, translation_language_code, root_path, directory_list)
    file_name_prefixes = generate_file_name_prefixes(root_path)
    return [
        tuple(
            new_project_paths[directory_list.index(directory)].joinpath(
                f"{file_name_prefix}_{directory}-{translation_language_code}-{username}.json"
            )
            for directory in directory_list
        )
        for file_name_prefix in file_name_prefixes
    ]


def create_project_file(segments_root_path: Path, new_file_path: Path):
    if not segments_root_path or not new_file_path or Path(new_file_path).exists():
        return False
    segment_ids = get_json_data(segments_root_path).keys()
    data = {key: "" for key in segment_ids}
    if not new_file_path.parent.exists():
        new_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(new_file_path, "w+") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return True


class OverrideException(Exception):
    pass
