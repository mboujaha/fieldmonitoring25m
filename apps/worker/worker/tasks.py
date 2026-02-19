from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from worker.celery_app import celery_app

logger = get_task_logger(__name__)


def _session() -> Session:
    return SessionLocal()


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hour_str, minute_str = value.split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
    except Exception as exc:
        raise ValueError("Invalid HH:MM time") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Invalid HH:MM time")
    return hour, minute


def _should_enqueue(field: Any, now_utc: datetime) -> bool:
    metadata = dict(field.metadata_json or {})
    schedule = metadata.get("schedule")
    if not isinstance(schedule, dict):
        schedule = {"enabled": True, "timezone": "UTC", "local_time": "06:00", "frequency": "daily"}

    if not schedule.get("enabled", True):
        return False

    tz_name = str(schedule.get("timezone") or "UTC")
    try:
        tz = ZoneInfo(tz_name) if ZoneInfo is not None else timezone.utc
    except Exception:
        tz = timezone.utc
        tz_name = "UTC"

    local_dt = now_utc.astimezone(tz)
    try:
        target_hour, target_minute = _parse_hhmm(str(schedule.get("local_time") or "06:00"))
    except ValueError:
        target_hour, target_minute = 6, 0

    if local_dt.hour != target_hour or (local_dt.minute // 5) != (target_minute // 5):
        return False

    frequency = str(schedule.get("frequency") or "daily").lower()
    if frequency == "weekly" and local_dt.weekday() != 0:
        return False

    today_key = local_dt.date().isoformat()
    last_run_key = str(schedule.get("last_run_local_date") or "")
    if last_run_key == today_key:
        return False

    schedule["timezone"] = tz_name
    schedule["last_run_local_date"] = today_key
    metadata["schedule"] = schedule
    field.metadata_json = metadata
    return True


@celery_app.task(name="worker.tasks.run_analysis_task")
def run_analysis_task(job_id: str) -> dict:
    from app.models import AnalysisJob, JobStatusEnum
    from app.services.analysis import run_analysis_job

    db = _session()
    try:
        job = db.get(AnalysisJob, uuid.UUID(job_id))
        if job is None:
            raise RuntimeError(f"Analysis job {job_id} not found")
        result = run_analysis_job(db, job)
        db.commit()
        return result
    except Exception as exc:
        logger.exception("Analysis task failed", exc_info=exc)
        job = db.get(AnalysisJob, uuid.UUID(job_id))
        if job is not None:
            job.status = JobStatusEnum.FAILED
            job.error_message = str(exc)
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(name="worker.tasks.run_export_task")
def run_export_task(export_id: str) -> dict:
    from app.models import ExportJob, JobStatusEnum
    from app.services.exports import run_export_job

    db = _session()
    try:
        export_job = db.get(ExportJob, uuid.UUID(export_id))
        if export_job is None:
            raise RuntimeError(f"Export job {export_id} not found")
        result = run_export_job(db, export_job)
        db.commit()
        return result
    except Exception as exc:
        logger.exception("Export task failed", exc_info=exc)
        export_job = db.get(ExportJob, uuid.UUID(export_id))
        if export_job is not None:
            export_job.status = JobStatusEnum.FAILED
            export_job.error_message = str(exc)
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(name="worker.tasks.run_sr_task")
def run_sr_task(payload: dict) -> dict:
    # SR inference queue placeholder for GPU workers.
    return {"status": "queued", "payload": payload}


@celery_app.task(name="worker.tasks.schedule_daily_attempts")
def schedule_daily_attempts() -> dict:
    from app.models import AnalysisJob, Field, JobStatusEnum

    db = _session()
    scheduled = 0
    try:
        fields = db.query(Field).all()
        now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        for field in fields:
            if not _should_enqueue(field, now_utc):
                continue
            job = AnalysisJob(
                field_id=field.id,
                requested_by_id=None,
                status=JobStatusEnum.QUEUED,
                queue="analysis_cpu",
                params_json={
                    "date_from": None,
                    "date_to": None,
                    "max_cloud": None,
                    "include_sr": False,
                    "include_radar_overlay": True,
                },
                result_json={},
            )
            db.add(job)
            db.flush()
            run_analysis_task.apply_async(args=[str(job.id)], queue="analysis_cpu")
            scheduled += 1
        db.commit()
        return {"scheduled": scheduled}
    finally:
        db.close()
