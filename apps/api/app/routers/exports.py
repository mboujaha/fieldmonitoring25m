from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user, require_org_role
from app.db.session import get_db
from app.models import ExportJob, Farm, Field, JobStatusEnum, RoleEnum, User
from app.schemas import ExportCreateRequest, ExportJobResponse
from app.services.queue import celery_client
from app.services.storage import create_presigned_get_url

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("", response_model=ExportJobResponse)
def create_export_job(
    payload: ExportCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExportJobResponse:
    field = db.get(Field, UUID(payload.field_id))
    if field is None:
        raise HTTPException(status_code=404, detail="Field not found")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")

    require_org_role(org_id=farm.organization_id, user_id=current_user.id, db=db, minimum=RoleEnum.ANALYST)

    export_job = ExportJob(
        field_id=field.id,
        requested_by_id=current_user.id,
        format=payload.format,
        status=JobStatusEnum.QUEUED,
        params_json={
            "layer_id": payload.layer_id,
            "index_name": payload.index_name,
            "source_mode": payload.source_mode,
            "observed_on": payload.observed_on,
        },
    )
    db.add(export_job)
    db.commit()

    celery_client.send_task("worker.tasks.run_export_task", args=[str(export_job.id)], queue="exports")

    return ExportJobResponse(
        id=str(export_job.id),
        status=export_job.status.value,
        format=export_job.format.value,
        error_message=export_job.error_message,
    )


@router.get("/{export_id}", response_model=ExportJobResponse)
def get_export_job(
    export_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExportJobResponse:
    export_job = db.get(ExportJob, export_id)
    if export_job is None:
        raise HTTPException(status_code=404, detail="Export job not found")

    field = db.get(Field, export_job.field_id)
    if field is None:
        raise HTTPException(status_code=404, detail="Field not found")

    farm = db.get(Farm, field.farm_id)
    if farm is None:
        raise HTTPException(status_code=404, detail="Farm not found")

    require_org_role(org_id=farm.organization_id, user_id=current_user.id, db=db)

    output_uri = None
    if export_job.output_uri:
        output_uri = create_presigned_get_url(export_job.output_uri, expires_seconds=3600, external=True)

    return ExportJobResponse(
        id=str(export_job.id),
        status=export_job.status.value,
        format=export_job.format.value,
        output_uri=output_uri,
        error_message=export_job.error_message,
    )
