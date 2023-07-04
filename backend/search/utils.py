import json
import os
from pathlib import Path
from typing import Generator

from app.core.config import settings


def get_ca_cert_path() -> Path:
    return Path(__file__).parent.parent / "ca.crt"


def get_json_data(file_path: Path) -> dict[str, str]:
    with open(file_path, "r") as f:
        return json.load(f)


def get_filename(file_path: Path) -> str:
    return file_path.name


def get_prefix(file_path: Path) -> str:
    return get_filename(file_path).split("_")[0]


def is_root_in_path(file_path: Path) -> bool:
    return "unpublished/root" in str(file_path)


def is_root(file_path: Path) -> bool:
    return get_filename(file_path).split("_")[1].split("-")[
        0
    ] == "root" and is_root_in_path(file_path)


def find_root_path(file_path: Path) -> Path | None:
    if is_root(file_path):
        return file_path

    prefix: str = get_prefix(file_path)
    prefixed_files: list[Path] = list(settings.WORK_DIR.glob(f"**/*{prefix}*"))

    for path in prefixed_files:
        if is_root_in_path(path):
            return path

    return None


def get_muid(file_path: Path) -> str:
    after_unpublished: tuple[str] = file_path.parts[
        file_path.parts.index("unpublished") + 1 :
    ]
    return "-".join(after_unpublished[:3])


def yield_file_path(work_dir: Path, level: int = 0) -> Generator[Path, None, None]:
    for file in os.listdir(work_dir):
        if file.startswith("."):
            continue
        full_path: Path = work_dir / file
        if full_path.is_dir():
            yield from yield_file_path(full_path, level + 1)
        elif level > 0 and full_path.is_file() and full_path.name.endswith(".json"):
            yield full_path
