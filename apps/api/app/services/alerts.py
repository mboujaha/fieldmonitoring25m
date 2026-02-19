from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import AlertEvent, AlertSeverityEnum, Field, Observation


def create_alert(
    db: Session,
    organization_id: str,
    field_id: str | None,
    severity: AlertSeverityEnum,
    category: str,
    message: str,
    metadata_json: dict | None = None,
) -> AlertEvent:
    org_uuid = organization_id if isinstance(organization_id, uuid.UUID) else uuid.UUID(str(organization_id))
    fld_uuid = None if field_id is None else (field_id if isinstance(field_id, uuid.UUID) else uuid.UUID(str(field_id)))
    alert = AlertEvent(
        organization_id=org_uuid,
        field_id=fld_uuid,
        severity=severity,
        category=category,
        message=message,
        metadata_json=metadata_json or {},
    )
    db.add(alert)
    db.flush()
    return alert


def maybe_create_ndvi_drop_alert(
    db: Session,
    organization_id: str,
    field: Field,
    current_observation: Observation,
) -> None:
    current_stats = current_observation.indices_native.get("NDVI", {}).get("stats") or {}
    current_mean = current_stats.get("mean")
    if current_mean is None:
        return

    previous = (
        db.query(Observation)
        .filter(Observation.field_id == field.id, Observation.id != current_observation.id)
        .order_by(Observation.observed_on.desc())
        .limit(5)
        .all()
    )
    prev_values: list[float] = []
    for obs in previous:
        value = (obs.indices_native.get("NDVI", {}).get("stats") or {}).get("mean")
        if value is not None:
            prev_values.append(float(value))

    if len(prev_values) < 3:
        return

    baseline = sum(prev_values[:3]) / 3
    delta = baseline - float(current_mean)
    if delta >= 0.20:
        create_alert(
            db=db,
            organization_id=organization_id,
            field_id=str(field.id),
            severity=AlertSeverityEnum.WARN,
            category="NDVI_DROP",
            message=f"NDVI dropped by {delta:.2f} against recent baseline.",
            metadata_json={"baseline": baseline, "current": current_mean, "delta": delta},
        )
