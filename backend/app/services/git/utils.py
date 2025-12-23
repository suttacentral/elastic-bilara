import contextlib
import subprocess

from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.db.schemas.user import UserBase
from app.services.git.manager import GitManager
from pygit2 import (
    GIT_STATUS_INDEX_NEW,
    GIT_STATUS_INDEX_MODIFIED,
    GIT_STATUS_INDEX_DELETED,
    GIT_STATUS_WT_MODIFIED,
    GIT_STATUS_WT_NEW,
    GIT_STATUS_WT_DELETED,
)
from pydantic import BaseModel


def get_project_title(branch: str) -> str:
    parts = branch.split("_")
    if len(parts) > 5:
        return "/".join(parts[:-1]) + "_" + parts[-1]
    return "/".join(parts)


def get_branch_name(manager: GitManager, file_paths: list[Path] = None) -> str:
    paths = file_paths or []
    if not paths:
        raise ValueError("No file paths provided.")
    project_head = get_project_head(paths[0])
    project_pr = manager.get_pr(project_head)
    file_heads = get_file_heads(paths)
    file_heads_prs = [manager.get_pr(head) for head in file_heads.values() if manager.get_pr(head)]
    changed_files_heads = [head for path, head in file_heads.items() if manager.has_changes(head, path)]

    if len(paths) == 1:
        if project_pr and GitManager.is_file_in_pr(project_pr, paths[0]):
            return project_head
        else:
            return list(file_heads.values())[0]

    if file_heads_prs:
        if changed_files_heads and len(changed_files_heads) == 1:
            return changed_files_heads[0]
    return project_head


def get_file_heads(paths: list[Path] = None) -> dict[Path, str]:
    return {path: "_".join(str(path).split("/")).removesuffix(".json") for path in paths} if paths else {}


def get_project_head(path: Path) -> str:
    parts: tuple = path.parts[:-1]
    if len(parts) == 6 and parts[-3] not in parts[-2]:
        return str(Path().joinpath(*parts[:-1])).replace("/", "_")
    elif len(parts) > 6 and parts[-3] in parts[-2]:
        return str(Path().joinpath(*parts[:-2])).replace("/", "_")
    return str(Path().joinpath(*parts)).replace("/", "_")


def clean_path(path: str) -> Path:
    return (
        Path(path.removeprefix("/app/checkouts/unpublished/"))
        if "/app/checkouts/unpublished/" in path
        else Path(path.removeprefix("checkouts/unpublished/"))
    )



def get_pr_commit_message(branch: str) -> str:
    return f"Publishing translations for {get_project_title(branch)}"


def get_pr_title(branch: str) -> str:
    return f"New translations for {get_project_title(branch)}"


def get_pr_body(user: UserBase) -> str:
    return (
        f"Request made by {user.username}\n\nPlease do not modify this branch directly. Changes should be\nmade "
        f"via the Bilara Translation App and the Pull Request\nupdated from Bilara."
    )


def find_mismatched_paths(file_paths: list[str] = None) -> tuple[bool, list[str]]:
    """
    Identify paths that don't match the most common project head in a list of file paths.

    The function determines the "project head" of each path, identifies the most common project head,
    and then finds paths that don't match this most common head.

    Args:
    - file_paths (list[str], optional): A list of file paths to check for mismatched project heads.
      Defaults to None.

    Returns: - tuple[bool, list[str]]: - A boolean indicating whether all paths have the same, most common project
    head (True if they match, False otherwise). - A list of mismatched paths that don't have the most common project
    head. If all paths match, the list is empty.

    Example: - For input ["directory1/directory2/file1", "directory1/directory2/file2",
    "directoryA/directoryB/file2"], if "directory1/directory2" is the most common project head, the function returns
    (False, ["/directoryA/directoryB/file2"]).
    """
    paths: list[Path] = [clean_path(path) for path in file_paths] if file_paths else []
    if not paths:
        return True, []
    project_heads: list[str] = [get_project_head(path) for path in paths]
    most_common_head, _ = Counter(project_heads).most_common(1)[0]
    mismatched_paths: list[str] = [f"/{path}" for path, head in zip(paths, project_heads) if head != most_common_head]
    return len(mismatched_paths) == 0, mismatched_paths


def ensure_safe_directory(repo_path: Path) -> None:
    repo_path_str = str(repo_path)
    with contextlib.suppress(subprocess.CalledProcessError):
        result = subprocess.run(
            ["git", "config", "--global", "--get-all", "safe.directory"],
            capture_output=True,
            text=True
        )

        if repo_path_str in result.stdout.splitlines():
            return

        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", repo_path_str],
            check=True,
            capture_output=True
        )


class FileStatus(BaseModel):
    path: str
    status: str
    status_code: int


class GitStatusResponse(BaseModel):
    files: list[FileStatus]
    total: int


class FileDiffResponse(BaseModel):
    path: str
    diff: str
    status: str


class DiscardRequest(BaseModel):
    file_path: str


class DiscardResponse(BaseModel):
    success: bool
    message: str
    file_path: str


def get_status_name(status_code: int) -> str:
    """Convert pygit2 status codes into readable status names."""
    status_map = {
        GIT_STATUS_INDEX_NEW: "staged_new",
        GIT_STATUS_INDEX_MODIFIED: "staged_modified",
        GIT_STATUS_INDEX_DELETED: "staged_deleted",
        GIT_STATUS_WT_NEW: "untracked",
        GIT_STATUS_WT_MODIFIED: "modified",
        GIT_STATUS_WT_DELETED: "deleted",
    }

    for code, name in status_map.items():
        if status_code & code:
            return name
    return "unknown"
