from app.core.config import settings
from celery import Celery

celery_app = Celery(
    "bilara", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_BACKEND_URL, include=["app.tasks"]
)

celery_app.conf.task_queues = {
    "pr_queue": {"exchange": "pr_queue", "routing_key": "pr_queue"},
    "commit_queue": {"exchange": "commit_queue", "routing_key": "commit_queue"}
}
