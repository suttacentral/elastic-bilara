from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.services.git.manager import GitManager
from app.services.users.schema import UserData


def get_project_title(branch: str) -> str:
    parts = branch.split("_")
    if len(parts) > 4:
        return "/".join(parts[:-1]) + "_" + parts[-1]
    return "/".join(parts)


def get_branch_name(user: UserData, file_paths: list[Path] = None) -> str:
    paths = file_paths or []
    manager = GitManager(settings.PUBLISHED_DIR, settings.WORK_DIR, user)
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
    return "_".join(str(path).split("/")[:4])


def clean_path(path: str) -> Path:
    return Path(path.removeprefix("/app/checkouts/unpublished/"))


def get_pr_commit_message(branch: str) -> str:
    return f"Publishing translations for {get_project_title(branch)}"


def get_pr_title(branch: str) -> str:
    return f"New translations for {get_project_title(branch)}"


def get_pr_body(user: UserData) -> str:
    return (
        f"Request made by {user.username}\n\nPlease do not modify this branch directly. Changes should be\nmade "
        f"via the Bilara Translation App and the Pull Request\nupdated from Bilara."
    )


def find_mismatched_paths(file_paths: list[str] = None) -> tuple[bool, list[str]]:
    paths: list[Path] = [clean_path(path) for path in file_paths] if file_paths else []
    project_heads: list[str] = [get_project_head(path) for path in paths]
    most_common_head, _ = Counter(project_heads).most_common(1)[0]
    mismatched_paths: list[str] = [head for head in project_heads if head != most_common_head]
    return len(mismatched_paths) == 0, mismatched_paths
