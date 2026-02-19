from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_client = Celery(
    "fieldmonitor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
