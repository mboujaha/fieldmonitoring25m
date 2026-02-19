import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import FeatureFlag


def is_enabled(db: Session, organization_id: str, key: str) -> bool:
    org_uuid = organization_id if isinstance(organization_id, uuid.UUID) else uuid.UUID(str(organization_id))
    flag = (
        db.query(FeatureFlag)
        .filter(FeatureFlag.organization_id == org_uuid, FeatureFlag.key == key)
        .one_or_none()
    )
    if flag is not None:
        return flag.enabled

    settings = get_settings()
    defaults = {
        "sr_analytics_enabled": settings.sr_analytics_default,
    }
    return defaults.get(key, False)
