from typing import Annotated

from app.db.schemas.user import UserBase
from app.services.auth import utils
from app.services.git.schema import PullRequestData
from app.services.git.utils import find_mismatched_paths
from app.services.users.utils import get_user
from app.tasks import pr
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/pr")


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_pull_request(user: Annotated[UserBase, Depends(utils.get_current_user)], paths: PullRequestData):
    is_consistent, mismatched_paths = find_mismatched_paths(paths.model_dump()["paths"])
    if not is_consistent:
        detail = {"error": "Paths must belong to the same project", "mismatched_paths": mismatched_paths}
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    user = get_user(int(user.github_id))
    result = pr.delay(user.model_dump(), paths.model_dump()["paths"])
    return {"detail": "Pull request creation has been scheduled", "task_id": result.id}


@router.post("/split-merge/", status_code=status.HTTP_201_CREATED)
async def create_pull_request_for_split_merge(
    user: Annotated[UserBase, Depends(utils.get_current_user)], paths: PullRequestData
):
    user = get_user(int(user.github_id))
    result = pr.delay(user.model_dump(), paths.model_dump()["paths"])
    return {"detail": "Pull request creation has been scheduled", "task_id": result.id}