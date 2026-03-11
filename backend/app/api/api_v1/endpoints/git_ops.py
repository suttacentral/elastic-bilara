import hashlib
import hmac
import json
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
from pydantic import BaseModel
from app.services.git.utils import (
    ensure_safe_directory,
    FileStatus,
    GitStatusResponse,
    FileDiffResponse,
    DiscardRequest,
    DiscardResponse,
    get_status_name
)


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


@router.get(
    "/status",
    response_model=GitStatusResponse,
    description="Get the git status of the unpublished repository",
    dependencies=[Depends(permissions.is_user_active)],
)
async def get_git_status(
    token_data: Annotated[TokenData, Depends(utils.get_current_user)],
) -> GitStatusResponse:
    """Get status of all modified files in unpublished repository.

    Admins see all files; regular users only see files whose path
    contains their username.
    """
    repo_path = settings.WORK_DIR
    ensure_safe_directory(repo_path)

    current_user: UserBase = get_user(int(token_data.github_id))
    is_admin = current_user.role in [Role.ADMIN.value, Role.SUPERUSER.value]

    try:
        repo = Repository(str(repo_path))

        files = []
        status_dict = repo.status()

        for filepath, status_code in status_dict.items():
            # 0 means unmodified
            if status_code != 0 and fileFilter(Path(filepath)):
                # Non-admin users can only see files in own namespace
                if (not is_admin and not _is_user_file_allowed(
                    filepath,
                    current_user.username,
                )):
                    continue
                files.append(FileStatus(
                    path=filepath,
                    status=get_status_name(status_code),
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
    description="Get the diff content of the specified file",
    dependencies=[Depends(permissions.is_user_active)],
)
async def get_file_diff(
    file_path: str,
    token_data: Annotated[TokenData, Depends(utils.get_current_user)],
) -> FileDiffResponse:
    """Get the diff of the specified file relative to HEAD.

    Non-admin users can only view diffs of files in their own namespace.

    Performance optimized: uses git command instead of pygit2
    diff iteration.
    """
    current_user: UserBase = get_user(int(token_data.github_id))
    is_admin = current_user.role in [Role.ADMIN.value, Role.SUPERUSER.value]

    repo_path = settings.WORK_DIR
    file_path = _validate_file_path(file_path, repo_path)

    if not is_admin and not _is_user_file_allowed(
        file_path,
        current_user.username,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this file's diff",
        )

    try:

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

        if not status_output:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File has no changes: {file_path}"
            )

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
                    ["git", "diff", "HEAD", "--", file_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False
                )
                diff_text = result.stdout
            else:
                # Modified file: show changes
                result = subprocess.run(
                    ["git", "diff", "HEAD", "--", file_path],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False
                )
                diff_text = result.stdout

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


@router.post(
    "/discard",
    response_model=DiscardResponse,
    description="Discard changes of the specified file",
    dependencies=[Depends(permissions.is_user_active)],
)
async def discard_file_changes(
    request: DiscardRequest,
    token_data: Annotated[TokenData, Depends(utils.get_current_user)],
) -> DiscardResponse:
    """Discard changes of the specified file, restoring it to the HEAD state.
    Non-admin users can only discard files in their own namespace.
    """
    current_user: UserBase = get_user(int(token_data.github_id))
    is_admin = current_user.role in [Role.ADMIN.value, Role.SUPERUSER.value]

    repo_path = settings.WORK_DIR
    file_path = _validate_file_path(request.file_path, repo_path)

    if not is_admin and not _is_user_file_allowed(
        file_path,
        current_user.username,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to discard changes to this file",
        )

    try:
        repo = Repository(str(repo_path))

        # Check file status
        try:
            status_code = repo.status_file(file_path)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found in repository: {file_path}"
            )

        if status_code == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File has no changes to discard: {file_path}"
            )

        full_path = repo_path / file_path

        # Handle different types of changes
        if status_code & GIT_STATUS_WT_NEW:
            # New file (untracked), delete directly
            if full_path.exists():
                try:
                    full_path.unlink()
                except FileNotFoundError:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Untracked file not found for deletion: {file_path}"
                    )
                except OSError as e:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to delete untracked file '{file_path}': {str(e)}"
                    )
                # If parent directories are empty, delete them as well
                parent = full_path.parent
                while parent != repo_path and parent.exists():
                    try:
                        parent.rmdir()  # Only delete if directory is empty
                        parent = parent.parent
                    except OSError:
                        break
            return DiscardResponse(
                success=True,
                message=f"Deleted untracked file: {file_path}",
                file_path=file_path
            )
        elif status_code & GIT_STATUS_WT_DELETED:
            # File deleted, restore from HEAD
            head_commit = repo.head.peel()
            try:
                blob = head_commit.tree[file_path]
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_bytes(blob.data)
            except KeyError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found in HEAD: {file_path}"
                )
            return DiscardResponse(
                success=True,
                message=f"Restored deleted file: {file_path}",
                file_path=file_path
            )
        elif status_code & GIT_STATUS_WT_MODIFIED:
            # File modified, restore from HEAD
            head_commit = repo.head.peel()
            try:
                blob = head_commit.tree[file_path]
                full_path.write_bytes(blob.data)
            except KeyError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found in HEAD: {file_path}"
                )
            return DiscardResponse(
                success=True,
                message=f"Discarded changes in: {file_path}",
                file_path=file_path
            )
        elif status_code & (GIT_STATUS_INDEX_NEW | GIT_STATUS_INDEX_MODIFIED | GIT_STATUS_INDEX_DELETED):
            # Staged changes, need to remove from index first, then restore working directory
            repo.index.remove(file_path)
            repo.index.write()

            if not (status_code & GIT_STATUS_INDEX_NEW):
                # If not a newly added file, restore from HEAD
                head_commit = repo.head.peel()
                try:
                    blob = head_commit.tree[file_path]
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_bytes(blob.data)
                except KeyError:
                    pass
            elif full_path.exists():
                # Newly added file, delete it
                full_path.unlink()

            return DiscardResponse(
                success=True,
                message=f"Discarded staged changes in: {file_path}",
                file_path=file_path
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown file status: {status_code}"
            )

    except GitError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Git error: {str(e)}"
        )


@router.post("/sync", status_code=status.HTTP_201_CREATED, description="Pull data from GitHub")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
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
    branch_name = (
        payload.get("pull_request").get("base").get("ref").removeprefix("refs/heads/")
        if payload.get("pull_request").get("base").get("ref")
        else None
    )

    if not GitManager.is_branch_protected(branch_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid branch name. Use 'published' or 'unpublished'"
        )
    user = get_user(int(payload["sender"]["id"]))
    result = pull.delay(user.model_dump(), branch_name, True, "origin")
    result_2 = push.delay(user.model_dump(), branch_name, "origin")
    return {"detail": "Sync action has been triggered", "task_id": [result.id, result_2.id]}


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
