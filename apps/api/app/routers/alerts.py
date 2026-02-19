from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.db.session import get_db
from app.models import AlertEvent, Field, Farm, Membership, User
from app.schemas import AlertResponse, AlertsClearResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
def list_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[AlertResponse]:
    org_ids = select(Membership.organization_id).where(Membership.user_id == current_user.id)
    alerts = (
        db.query(AlertEvent)
        .filter(AlertEvent.organization_id.in_(org_ids))
        .order_by(AlertEvent.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        AlertResponse(
            id=str(alert.id),
            organization_id=str(alert.organization_id),
            field_id=str(alert.field_id) if alert.field_id else None,
            severity=alert.severity.value,
            category=alert.category,
            message=alert.message,
            acknowledged_at=alert.acknowledged_at,
            metadata_json=alert.metadata_json,
        )
        for alert in alerts
    ]


@router.post("/{alert_id}/ack", response_model=AlertResponse)
def ack_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertResponse:
    alert = db.get(AlertEvent, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    membership = (
        db.query(Membership)
        .filter(Membership.organization_id == alert.organization_id, Membership.user_id == current_user.id)
        .one_or_none()
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Not allowed")

    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by_id = current_user.id
    db.commit()

    return AlertResponse(
        id=str(alert.id),
        organization_id=str(alert.organization_id),
        field_id=str(alert.field_id) if alert.field_id else None,
        severity=alert.severity.value,
        category=alert.category,
        message=alert.message,
        acknowledged_at=alert.acknowledged_at,
        metadata_json=alert.metadata_json,
    )


@router.delete("", response_model=AlertsClearResponse)
def clear_alerts(
    field_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertsClearResponse:
    org_ids = select(Membership.organization_id).where(Membership.user_id == current_user.id)
    query = db.query(AlertEvent).filter(AlertEvent.organization_id.in_(org_ids))

    if field_id:
        field = db.get(Field, field_id)
        if field is None:
            raise HTTPException(status_code=404, detail="Field not found")
        farm = db.get(Farm, field.farm_id)
        if farm is None:
            raise HTTPException(status_code=404, detail="Farm not found")
        membership = (
            db.query(Membership)
            .filter(Membership.organization_id == farm.organization_id, Membership.user_id == current_user.id)
            .one_or_none()
        )
        if membership is None:
            raise HTTPException(status_code=403, detail="Not allowed")
        query = query.filter(AlertEvent.field_id == field.id)

    deleted_alerts = query.delete(synchronize_session=False)
    db.commit()
    return AlertsClearResponse(deleted_alerts=deleted_alerts)
