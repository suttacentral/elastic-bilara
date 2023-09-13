from typing import Annotated

from app.celery import celery_app as app
from app.db.schemas.user import UserBase
from app.services.auth import utils
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/tasks")


@router.get("/{task_id}/")
async def get_task_status(user: Annotated[UserBase, Depends(utils.get_current_user)], task_id: str):
    return {"status": app.AsyncResult(task_id).status}
