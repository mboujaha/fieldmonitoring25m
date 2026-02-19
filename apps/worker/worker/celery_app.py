from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "fieldmonitor_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_routes={
        "worker.tasks.run_analysis_task": {"queue": "analysis_cpu"},
        "worker.tasks.run_export_task": {"queue": "exports"},
        "worker.tasks.run_sr_task": {"queue": "sr_gpu"},
        "worker.tasks.schedule_daily_attempts": {"queue": "analysis_cpu"},
    },
    beat_schedule={
        "daily-monitoring-attempts": {
            "task": "worker.tasks.schedule_daily_attempts",
            "schedule": 300.0,
        }
    },
    timezone="UTC",
)
