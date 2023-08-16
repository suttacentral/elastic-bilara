from app.celery import celery_app as app
from fastapi import APIRouter

router = APIRouter(prefix="/tasks")


@router.get("/{task_id}/")
async def get_task_status(task_id: str):
    return {"status": app.AsyncResult(task_id).status}
