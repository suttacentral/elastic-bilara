import hashlib
import hmac
import json
import logging
import subprocess
import urllib.parse
from pathlib import Path
from typing import Annotated

from app.core.config import settings
from app.db.models.user import Role
from app.db.schemas.user import UserBase
from app.services.auth import utils
from app.services.auth.schema import TokenData
from app.services.git.manager import GitManager
from app.services.users import permissions
from app.services.users.utils import get_user
from app.tasks import commit, pull, push
from search.utils import get_json_data, muid_from_relative_path
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pygit2 import (
    GitError,
    Repository,
    GIT_STATUS_INDEX_NEW,
    GIT_STATUS_INDEX_MODIFIED,
    GIT_STATUS_INDEX_DELETED,
    GIT_STATUS_WT_MODIFIED,
    GIT_STATUS_WT_NEW,
    GIT_STATUS_WT_DELETED,
)
from pydantic import BaseModel, ValidationError
from app.services.git.utils import (
    ensure_safe_directory,
    FileStatus,
    GitStatusResponse,
    FileDiffResponse,
    get_status_name
)

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/git")


def _validate_file_path(file_path: str, repo_path: Path) -> str:
    """Validate that file_path is a safe relative path within the repository.

    Raises HTTPException if the path attempts directory traversal or
    resolves outside the repository root.
    """
    if not file_path or file_path.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File path cannot be empty",
        )
    # Reject absolute paths and null bytes
    if file_path.startswith("/") or "\x00" in file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path",
        )
    # Resolve and verify it stays inside the repo.
    repo_root = repo_path.resolve()
    candidate = repo_root / file_path
    resolved = candidate.resolve()
    if not resolved.is_relative_to(repo_root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path: path escapes repository",
        )

    # Block symlink-based traversal for existing target or parent paths.
    for parent in [candidate, *candidate.parents]:
        if parent == repo_root:
            break
        if parent.exists() and parent.is_symlink():
            if not parent.resolve().is_relative_to(repo_root):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file path: symlink escapes repository",
                )

    return resolved.relative_to(repo_root).as_posix()


def _is_user_file_allowed(file_path: str, username: str) -> bool:
    """Return True if the file path belongs to the user's namespace."""
    username_lower = username.lower()
    return any(part.lower() == username_lower for part in Path(file_path).parts)


def _can_user_access_file(
    file_path: str, user: UserBase, *, projects: list[dict] | None = None
) -> bool:
    if _is_user_file_allowed(file_path, user.username):
        return True

    muid = muid_from_relative_path(file_path)
    if not muid:
        return False

    return permissions.can_edit_translation(
        int(user.github_id), muid, projects=projects, user=user
    )


def _has_meaningful_json_value(value) -> bool:
    if isinstance(value, dict):
        return any(_has_meaningful_json_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_meaningful_json_value(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def _is_meaningful_untracked_file(repo_path: Path, file_path: str) -> bool:
    """Exclude untouched blank templates while keeping actual new content."""
    relative_path = Path(file_path)
    if not relative_path.parts or relative_path.parts[0] not in {"translation", "comment", "tag"}:
        return True
    if relative_path.suffix.lower() != ".json":
        return True

    try:
        data = json.loads((repo_path / relative_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True

    return _has_meaningful_json_value(data)


def _get_base_published_ref(repo_path: Path, repo: Repository | None = None) -> str:
    """Return the base published reference to compare against ('origin/published', 'published', or 'HEAD')."""
    if repo is not None:
        try:
            if "refs/remotes/origin/published" in repo.references:
                return "origin/published"
            if "refs/heads/published" in repo.references:
                return "published"
        except Exception:
            pass
    return "origin/published" if (repo_path / ".git" / "refs" / "remotes" / "origin" / "published").exists() else "HEAD"


@router.get(
    "/status",
    response_model=GitStatusResponse,
    description="Get the git status of the unpublished repository (Publication Queue)",
    dependencies=[Depends(permissions.is_user_active)],
)
async def get_git_status(
    token_data: Annotated[TokenData, Depends(utils.get_current_user)],
    include_other_users: bool = False,
) -> GitStatusResponse:
    """Get modified files in the unpublished repository.

    Users, including admins, see their own namespace by default.
    Admins may explicitly request other users' files.
    """
    repo_path = settings.WORK_DIR
    ensure_safe_directory(repo_path)

    current_user: UserBase = get_user(int(token_data.github_id))
    is_admin = current_user.role in [Role.ADMIN.value, Role.SUPERUSER.value]
    show_other_users = is_admin and include_other_users

    projects: list[dict] | None = None
    if not is_admin and not show_other_users:
        projects = get_json_data(settings.WORK_DIR / "_project-v2.json")

    try:
        repo = Repository(str(repo_path))
        file_status_map: dict[str, tuple[str, int]] = {}
        base_ref = _get_base_published_ref(repo_path, repo)

        # 1. Check branch differences against base published ref
        if base_ref != "HEAD":
            try:
                diff_res = subprocess.run(
                    ["git", "diff", "--name-status", base_ref],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Git branch diff timed out",
                )
            if diff_res.returncode != 0:
                logger.error(
                    "git diff --name-status %s failed in %s: %s",
                    base_ref,
                    repo_path,
                    diff_res.stderr[:500],
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to compare against published branch: {diff_res.stderr[:200]}",
                )
            if diff_res.returncode == 0:
                status_code_map = {
                    "M": ("modified", GIT_STATUS_WT_MODIFIED),
                    "A": ("staged_new", GIT_STATUS_INDEX_NEW),
                    "D": ("deleted", GIT_STATUS_WT_DELETED),
                }
                for line in diff_res.stdout.strip().splitlines():
                    if not line:
                        continue
                    parts = line.split(maxsplit=1)
                    code = parts[0][0]
                    filepath = parts[1].split("\t")[-1].strip()
                    status_name, status_code = status_code_map.get(code, ("modified", GIT_STATUS_WT_MODIFIED))
                    file_status_map[filepath] = (status_name, status_code)

        # 2. Check local working tree status (for uncommitted or newly created files)
        status_dict = repo.status(untracked_files="all")
        for filepath, status_code in status_dict.items():
            if status_code == 0:
                continue
            status_name = get_status_name(status_code)
            file_status_map[filepath] = (status_name, status_code)

        files = []
        for filepath, (status_name, status_code) in file_status_map.items():
            if not fileFilter(Path(filepath)):
                continue
            if not show_other_users:
                can_access = (
                    _is_user_file_allowed(filepath, current_user.username)
                    if is_admin
                    else _can_user_access_file(filepath, current_user, projects=projects)
                )
                if not can_access:
                    continue
            if (
                (status_code & GIT_STATUS_WT_NEW)
                and not (status_code & GIT_STATUS_INDEX_NEW)
                and not _is_meaningful_untracked_file(repo_path, filepath)
            ):
                continue
            files.append(FileStatus(
                path=filepath,
                status=status_name,
                status_code=status_code
            ))

        # Sort by path
        files.sort(key=lambda x: x.path)

        return GitStatusResponse(files=files, total=len(files))
    except GitError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Git error: {str(e)}",
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {str(e)}",
        ) from e
    except OSError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OS error: {str(e)}",
        ) from e


def fileFilter(filepath: Path) -> bool:
    """Filter out hidden files and directories."""
    return not any(part.startswith('.') for part in filepath.parts) and not any(part.startswith('_') for part in filepath.parts)


@router.get(
    "/diff/{file_path:path}",
    response_model=FileDiffResponse,
    description="Get the diff content of the specified file relative to published",
    dependencies=[Depends(permissions.is_user_active)],
)
async def get_file_diff(
    file_path: str,
    token_data: Annotated[TokenData, Depends(utils.get_current_user)],
) -> FileDiffResponse:
    """Get the diff of the specified file relative to the published base branch.

    Non-admin users can only view diffs of files in their own namespace.

    Performance optimized: uses git command instead of pygit2
    diff iteration.
    """
    current_user: UserBase = get_user(int(token_data.github_id))
    is_admin = current_user.role in [Role.ADMIN.value, Role.SUPERUSER.value]

    repo_path = settings.WORK_DIR
    file_path = _validate_file_path(file_path, repo_path)

    if not is_admin and not _can_user_access_file(file_path, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this file's diff",
        )

    try:
        repo = None
        try:
            repo = Repository(str(repo_path))
        except Exception:
            pass
        base_ref = _get_base_published_ref(repo_path, repo)
        ref_to_use = base_ref if base_ref != "HEAD" else "HEAD"

        # Quick check file status using git command (faster than pygit2)
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "--", file_path],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Status check timed out for: {file_path}"
            )

        # Keep leading spaces because porcelain status uses them as signal.
        status_output = result.stdout.rstrip()

        # Parse status code (first 2 characters)
        status_code = (
            status_output[:2] if len(status_output) >= 2 else "  "
        )

        # Map git status to our status names
        status_map = {
            ' M': 'modified',
            'M ': 'staged_modified',
            'MM': 'modified',
            '??': 'untracked',
            ' D': 'deleted',
            'D ': 'staged_deleted',
            'A ': 'staged_new',
            'AM': 'staged_modified',
        }
        status_name = status_map.get(status_code, 'modified')

        # When working tree is clean, infer status from branch diff
        if not status_output:
            try:
                branch_diff = subprocess.run(
                    ["git", "diff", "--name-status", ref_to_use, "--", file_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                if branch_diff.returncode == 0 and branch_diff.stdout.strip():
                    branch_code = branch_diff.stdout.strip().split()[0][0]
                    branch_status_map = {
                        'A': 'staged_new',
                        'M': 'modified',
                        'D': 'deleted',
                    }
                    status_name = branch_status_map.get(branch_code, 'modified')
            except subprocess.TimeoutExpired:
                pass

        # Get diff using git command (5-10x faster than pygit2 iteration)
        diff_text = ""

        try:
            if '?' in status_code:
                # New untracked file: show full content as diff
                result = subprocess.run(
                    ["git", "diff", "--no-index", "--", "/dev/null", file_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False
                )
                diff_text = result.stdout
            elif 'D' in status_code:
                # Deleted file: show what was removed
                result = subprocess.run(
                    ["git", "diff", ref_to_use, "--", file_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False
                )
                diff_text = result.stdout
            else:
                # Modified or committed file: show changes relative to base_ref / HEAD
                result = subprocess.run(
                    ["git", "diff", ref_to_use, "--", file_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False
                )
                diff_text = result.stdout

                if not status_output and not diff_text:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File has no changes: {file_path}"
                    )

        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Diff generation timed out for: {file_path}"
            )

        # Limit diff size to prevent frontend freezing on huge files
        max_lines = 5000
        lines = diff_text.split('\n')
        if len(lines) > max_lines:
            truncated_count = len(lines) - max_lines
            diff_text = (
                '\n'.join(lines[:max_lines]) +
                f'\n\n... (truncated, {truncated_count} more lines)'
            )

        return FileDiffResponse(
            path=file_path,
            diff=diff_text,
            status=status_name
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating diff: {str(e)}"
        )


@router.post("/sync", status_code=status.HTTP_201_CREATED, description="Pull data from GitHub")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str | None = Header(None),
) -> dict:
    payload_bytes = await request.body()
    secret = settings.GITHUB_WEBHOOK_SECRET.encode()
    expected_signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()

    if (
        not x_hub_signature_256
        or not x_hub_signature_256.startswith("sha256=")
        or not hmac.compare_digest(
            f"sha256={expected_signature}",
            x_hub_signature_256,
        )
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = parse_payload(payload_bytes.decode())

    if x_github_event and x_github_event != "pull_request":
        return {"detail": "Webhook event ignored"}

    try:
        webhook_payload = GitHubPullRequestPayload.model_validate(payload)
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pull request payload",
        )

    branch_name = webhook_payload.pull_request.base.ref.removeprefix("refs/heads/")

    if not GitManager.is_branch_protected(branch_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid branch name. Use 'published' or 'unpublished'"
        )
    user = get_user(webhook_payload.sender.id)
    result = pull.delay(user.model_dump(), branch_name, True, "origin")
    result_2 = push.delay(user.model_dump(), branch_name, "origin")
    return {"detail": "Sync action has been triggered", "task_id": [result.id, result_2.id]}


class GitHubPullRequestBase(BaseModel):
    ref: str


class GitHubPullRequest(BaseModel):
    base: GitHubPullRequestBase


class GitHubSender(BaseModel):
    id: int


class GitHubPullRequestPayload(BaseModel):
    pull_request: GitHubPullRequest
    sender: GitHubSender


@router.get(
    "/sync/{branch_name}",
    status_code=status.HTTP_201_CREATED,
    description="Pull data from GitHub",
    dependencies=[Depends(permissions.is_admin_or_superuser), Depends(permissions.is_user_active)],
)
async def sync_repository_data(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    branch_name: str = "published",
    force: bool = False,
) -> dict:
    if not GitManager.is_branch_protected(branch_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid branch name. Use 'published' or 'unpublished'"
        )
    user = get_user(int(user.github_id))
    result = pull.delay(user.model_dump(), branch_name, force, "origin")
    result_2 = push.delay(user.model_dump(), branch_name, "origin")

    return {"detail": "Sync action has been triggered", "task_id": [result.id, result_2.id]}


def parse_payload(payload: str) -> dict:
    payload_query_str = urllib.parse.unquote(payload)
    payload_json_str = payload_query_str.split("=", 1)[1]
    payload_dict = json.loads(payload_json_str)
    return payload_dict


class CommitRequest(BaseModel):
    file_paths: list[str]
    message: str


class CommitResponse(BaseModel):
    task_id: str
    detail: str


@router.post(
    "/commit",
    response_model=CommitResponse,
    status_code=status.HTTP_201_CREATED,
    description="Commit and push selected files to the unpublished repository",
    dependencies=[Depends(permissions.is_admin_or_superuser), Depends(permissions.is_user_active)],
)
async def commit_files(
    request: CommitRequest,
    user: Annotated[UserBase, Depends(utils.get_current_user)],
) -> CommitResponse:
    """Commit and push selected files to the unpublished repository"""
    if not request.file_paths:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_paths cannot be empty"
        )

    if not request.message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="commit message cannot be empty"
        )

    user_data = get_user(int(user.github_id))
    result = commit.delay(user_data.model_dump(), request.file_paths, request.message, add=True)

    return CommitResponse(
        task_id=result.id,
        detail=f"Commit task has been triggered for {len(request.file_paths)} file(s)"
    )
