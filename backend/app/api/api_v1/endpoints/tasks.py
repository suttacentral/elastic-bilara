from typing import Annotated

from app.celery import celery_app as app
from app.services.auth import utils
from app.services.users.schema import UserData
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/tasks")


@router.get("/{task_id}/")
async def get_task_status(user: Annotated[UserData, Depends(utils.get_current_user)], task_id: str):
    return {"status": app.AsyncResult(task_id).status}
