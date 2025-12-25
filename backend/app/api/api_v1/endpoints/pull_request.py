from typing import Annotated

from app.db.schemas.user import UserBase
from app.services.auth import utils
from app.services.git.schema import PullRequestData
from app.services.git.utils import find_mismatched_paths
from app.services.users.utils import get_user
from app.tasks import pr
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/pr")


def _create_pr_task(
    user: UserBase,
    paths: PullRequestData,
    validate_paths: bool = True,
):
    """
    Internal helper to create a pull request task.

    Args:
        user: Authenticated user
        paths: Pull request data with file paths
        validate_paths: Whether to validate path consistency

    Returns:
        dict: Task details with task_id

    Raises:
        HTTPException: If path validation fails
    """
    file_paths = paths.model_dump()["paths"]

    if validate_paths:
        is_consistent, mismatched = find_mismatched_paths(file_paths)
        if not is_consistent:
            detail = {
                "error": "Paths must belong to the same project",
                "mismatched_paths": mismatched,
            }
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail,
            )

    user_data = get_user(int(user.github_id))
    result = pr.delay(user_data.model_dump(), file_paths)

    return {
        "detail": "Pull request creation has been scheduled",
        "task_id": result.id,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_pull_request(
    user: Annotated[UserBase, Depends(utils.get_current_user)],
    paths: PullRequestData,
):
    """
    Create a standard pull request.

    Validates that all paths belong to the same project.

    Args:
        user: Authenticated user
        paths: File paths for the pull request

    Returns:
        dict: Task confirmation and ID
    """
    return _create_pr_task(user, paths, validate_paths=True)

