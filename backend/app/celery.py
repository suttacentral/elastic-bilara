from app.core.config import settings
from celery import Celery

celery_app = Celery(
    "bilara", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_BACKEND_URL, include=["app.tasks"]
)
