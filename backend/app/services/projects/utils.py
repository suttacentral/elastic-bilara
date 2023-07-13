import json
import re
from pathlib import Path

from search.search import Search
from search.utils import get_json_data

search = Search()


def sort_paths(paths: set[str]) -> list[str]:
    def extract_key(s):
        head = s.rsplit("/", 1)[-1]
        head_parts = re.split(r"(\d+)", head)
        return [int(part) if part.isdigit() else part for part in head_parts]

    return sorted(paths, key=extract_key)


def update_file(path: Path, data: dict[str, str], root_path: Path) -> tuple[bool, Exception | None]:
    root_data: dict[str, str] = get_json_data(root_path)

    for key in data:
        if key not in root_data:
            return False, KeyError(f"{key} not found in the root file")

    file_data: dict[str, str] = get_json_data(path)

    original_data: dict[str, str] = file_data.copy()

    for key, value in data.items():
        file_data[key] = value

    updated, elastic_error = search.update_segments(path, file_data)

    if elastic_error:
        return False, elastic_error

    written, file_error = write_json_data(path, file_data)

    if file_error:
        updated = False
        while not updated:
            updated, _ = search.update_segments(path, original_data)
        return False, file_error

    return True, None


def write_json_data(path: Path, data: dict[str, str]) -> tuple[bool, Exception | None]:
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    except (OSError, TypeError) as e:
        return False, e
    return True, None
