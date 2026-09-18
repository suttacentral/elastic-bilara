import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.text_types import TextType
from app.db.schemas.user import User, UserBase
from app.services.git import utils
from app.services.projects.virtual_projects import VirtualProjectFile
from app.services.projects.file_coordinator import project_file_lock
from app.services.projects.structure_store import StructureStore, StructureConflict
from app.services.users.utils import get_user
from app.tasks import commit
from search.search import Search
from search.utils import find_root_path, get_json_data

search = Search()

@dataclass(frozen=True)
class SplitMergePublishResult:
    task_id: str | None
    auto_published_paths: list[str]
    manual_publish_paths: list[str]


def _relative_split_merge_path(path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(settings.WORK_DIR.resolve())
        except ValueError:
            parts = path.parts
            if "unpublished" in parts:
                return Path(*parts[parts.index("unpublished") + 1:])
    return Path(str(path).lstrip("/"))


def format_split_merge_publish_path(path: Path) -> str:
    return f"/{_relative_split_merge_path(path).as_posix()}"


def get_split_merge_text_type(path: Path) -> str:
    relative_path = _relative_split_merge_path(path)
    return relative_path.parts[0] if relative_path.parts else ""


def schedule_split_merge_auto_publish(
    user: UserBase,
    paths: list[Path] | set[Path] | tuple[Path, ...],
    operation: str,
) -> SplitMergePublishResult:
    commit_paths = list(dict.fromkeys(_relative_split_merge_path(path).as_posix() for path in paths))
    task_id = None
    if commit_paths:
        user_data = get_user(int(user.github_id))
        message = f"{user.username} {operation} split/merge files"
        result = commit.delay(user_data.model_dump(), commit_paths, message)
        task_id = result.id
    return SplitMergePublishResult(
        task_id=task_id,
        auto_published_paths=[f"/{path}" for path in commit_paths],
        manual_publish_paths=[],
    )


def sort_paths(paths: set[str]) -> list[str]:
    def extract_key(s):
        head = s.rsplit("/", 1)[-1]
        head_parts = re.split(r"(\d+)", head)
        return [int(part) if part.isdigit() else part for part in head_parts]

    return sorted(paths, key=extract_key)


def _update_file_locked(
    path: Path,
    data: dict[str, str],
    root_data: dict[str, str],
) -> tuple[bool, Exception | None]:
    for key in data:
        if key not in root_data:
            return False, KeyError(f"{key} not found in the root file")

    file_data: dict[str, str] = get_json_data(path)
    original_data: dict[str, str] = file_data.copy()
    file_data.update(data)

    _, elastic_error = search.update_segments(path, file_data)
    if elastic_error:
        return False, elastic_error

    written, file_error = write_json_data(path, file_data)
    if not file_error:
        return written, None

    restored, rollback_error = search.update_segments(path, original_data)
    if not restored:
        return False, RuntimeError(
            f"{file_error}; search rollback failed: {rollback_error}"
        )
    return False, file_error


def _schedule_file_commit(path: Path, user: UserBase) -> str:
    cleaned_path = str(utils.clean_path(str(path)))
    result = commit.delay(
        user.model_dump(),
        [cleaned_path],
        f"Translations by {user.username} to {cleaned_path}",
    )
    return result.id


def update_file(
    path: Path, data: dict[str, str], root_path: Path, user: UserBase,
    structure_revision: str | None = None,
) -> tuple[bool, Exception | None, str | None]:
    stored_user: UserBase = get_user(int(user.github_id))

    store = StructureStore(settings.WORK_DIR, root_path)
    try:
        with store.lock(), project_file_lock(path):
            store.check_ready()
            root_data = get_json_data(root_path)
            store.check_revision(structure_revision, root_data)
            updated, error = _update_file_locked(path, data, root_data)
    except StructureConflict as error:
        return False, error, None

    if error:
        return False, error, None

    task_id = _schedule_file_commit(path, stored_user) if updated else None
    return True, None, task_id


def materialize_translation_file(
    virtual_file: VirtualProjectFile,
    data: dict[str, str],
    user: UserBase,
    structure_revision: str | None = None,
) -> tuple[bool, Exception | None, str | None, bool]:
    store = StructureStore(settings.WORK_DIR, virtual_file.source_path)
    try:
        with store.lock():
            store.check_ready()
            root_data = get_json_data(virtual_file.source_path)
            store.check_revision(structure_revision, root_data)
            return _materialize_translation_file_locked(virtual_file, data, user, root_data)
    except StructureConflict as error:
        return False, error, None, False


def _materialize_translation_file_locked(virtual_file, data, user, root_data):
    """Save a configured translation, creating its file on the first nonblank save."""
    if not isinstance(root_data, dict):
        error = TypeError(
            f"Expected root file to contain a JSON object: {virtual_file.source_path}"
        )
        return False, error, None, False

    unknown_keys = set(data) - set(root_data)
    if unknown_keys:
        unknown_key = sorted(unknown_keys)[0]
        return False, KeyError(f"{unknown_key} not found in the root file"), None, False

    target_path = virtual_file.target_path
    temporary_path = None
    created = False

    with project_file_lock(target_path):
        try:
            if target_path.exists():
                stored_user = get_user(int(user.github_id))
                updated, error = _update_file_locked(
                    target_path,
                    data,
                    root_data,
                )
                if error:
                    return False, error, None, True
                task_id = (
                    _schedule_file_commit(target_path, stored_user) if updated else None
                )
                return True, None, task_id, True

            if not any(value and value.strip() for value in data.values()):
                return True, None, None, False

            complete_data = {uid: "" for uid in root_data}
            complete_data.update(data)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target_path.parent,
                prefix=f".{target_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                json.dump(complete_data, temporary_file, indent=2, ensure_ascii=False)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_path = Path(temporary_file.name)

            os.link(temporary_path, target_path)
            created = True
            temporary_path.unlink(missing_ok=True)

            indexed, index_error = search.add_to_index(target_path)
            if not indexed:
                raise index_error or RuntimeError(
                    "Failed to index materialized translation file"
                )

            stored_user = get_user(int(user.github_id))
            task_id = _schedule_file_commit(target_path, stored_user)
            return True, None, task_id, True
        except Exception as error:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)
            if created:
                target_path.unlink(missing_ok=True)
                try:
                    removed, cleanup_error = search.remove_segments(target_path)
                    if not removed:
                        raise cleanup_error or RuntimeError(
                            "Failed to roll back search indexes"
                        )
                except Exception as cleanup_error:
                    error = RuntimeError(
                        f"{error}; index rollback failed: {cleanup_error}"
                    )
            return False, error, None, False


def write_json_data(path: Path, data: dict[str, str]) -> tuple[bool, Exception | None]:
    temporary_path = None
    try:
        target_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(
                sort_data(data, path), temporary_file, indent=2, ensure_ascii=False
            )
            os.fchmod(temporary_file.fileno(), target_mode)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)

        os.replace(temporary_path, path)
    except (OSError, TypeError) as e:
        return False, e
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
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


def compute_target_path(
    source_file: Path, root_path: Path, username: str, translation_language: str, directory_type: str
) -> Path:
    """Compute the target path for a single source file.

    Given a source file like:
        WORK_DIR/root/pli/ms/sutta/dn/dn1_root-pli-ms.json
    and root_path:
        WORK_DIR/root/pli/ms/sutta/

    This produces:
        WORK_DIR/translation/{lang}/{user}/sutta/dn/dn1_translation-{lang}-{user}.json
    """
    root_base = root_path.parent if root_path.suffix == ".json" else root_path
    root_parts = root_base.parts
    if "root" not in root_parts:
        raise ValueError(f'Expected "root" in path parts for {root_base!s}')
    root_index = root_parts.index("root")
    # Skip root/{lang}/{edition}/ (3 levels after "root") to get content-relative path
    content_base = Path(*root_parts[root_index + 3 :]) if len(root_parts) > root_index + 3 else Path(".")
    # Get the relative path of the source file's directory from root_path
    relative_dir = source_file.parent.relative_to(root_base) if source_file.parent != root_base else Path(".")
    prefix = source_file.name.split("_")[0]
    filename = f"{prefix}_{directory_type}-{translation_language}-{username}.json"
    target_dir = (
        settings.WORK_DIR
        / directory_type
        / translation_language.lower()
        / username.lower()
        / content_base
        / relative_dir
    )
    return target_dir / filename


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
