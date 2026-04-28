from typing import Annotated

from app.celery import celery_app as app
from app.db.schemas.user import UserBase
from app.services.auth import utils
from celery import states
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/tasks")


@router.get("/{task_id}/")
async def get_task_status(user: Annotated[UserBase, Depends(utils.get_current_user)], task_id: str):
    async_result = app.AsyncResult(task_id)
    response = {"status": async_result.status}
    if async_result.status == "PROGRESS":
        response["info"] = async_result.info
    elif async_result.status == states.FAILURE:
        response["error"] = getattr(async_result.result, "message", str(async_result.result))
    elif async_result.ready():
        response["result"] = async_result.result
    return response
