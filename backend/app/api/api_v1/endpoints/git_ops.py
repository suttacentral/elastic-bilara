import hashlib
import hmac
import json
import urllib.parse
from typing import Annotated

from app.core.config import settings
from app.db.schemas.user import UserBase
from app.services.auth import utils
from app.services.git.manager import GitManager
from app.services.users import permissions
from app.services.users.utils import get_user
from app.tasks import pull, push
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pygit2 import GitError, Repository

router = APIRouter(prefix="/git")


@router.post("/sync", status_code=status.HTTP_201_CREATED, description="Pull data from GitHub")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
) -> dict:
    payload_bytes = await request.body()
    secret = settings.GITHUB_WEBHOOK_SECRET.encode()
    expected_signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(f"sha256={expected_signature}", x_hub_signature_256):
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
