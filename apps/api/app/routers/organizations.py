import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, require_org_role
from app.db.session import get_db
from app.models import FeatureFlag, Invite, Membership, Organization, RoleEnum, User
from app.schemas import (
    FeatureFlagResponse,
    FeatureFlagUpdateRequest,
    InviteCreateRequest,
    InviteResponse,
    OrganizationCreateRequest,
    OrganizationResponse,
)

router = APIRouter(prefix="/orgs", tags=["organizations"])


@router.post("", response_model=OrganizationResponse)
def create_organization(
    payload: OrganizationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationResponse:
    existing = db.query(Organization).filter(Organization.name == payload.name).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization name already exists")

    org = Organization(name=payload.name, created_by_id=current_user.id)
    db.add(org)
    db.flush()
    db.add(Membership(organization_id=org.id, user_id=current_user.id, role=RoleEnum.OWNER))
    db.commit()
    return OrganizationResponse(id=str(org.id), name=org.name, created_at=org.created_at)


@router.post("/{org_id}/invites", response_model=InviteResponse)
def create_invite(
    org_id: UUID,
    payload: InviteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InviteResponse:
    require_org_role(org_id=org_id, user_id=current_user.id, db=db, minimum=RoleEnum.ADMIN)

    invite = Invite(
        organization_id=org_id,
        email=payload.email.lower(),
        role=payload.role,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    db.commit()
    return InviteResponse(
        id=str(invite.id),
        email=invite.email,
        role=invite.role,
        status=invite.status.value,
        expires_at=invite.expires_at,
    )


@router.get("/{org_id}/feature-flags", response_model=list[FeatureFlagResponse])
def list_feature_flags(
    org_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FeatureFlagResponse]:
    require_org_role(org_id=org_id, user_id=current_user.id, db=db, minimum=RoleEnum.ADMIN)
    flags = db.query(FeatureFlag).filter(FeatureFlag.organization_id == org_id).order_by(FeatureFlag.key.asc()).all()
    return [FeatureFlagResponse(key=flag.key, enabled=flag.enabled) for flag in flags]


@router.put("/{org_id}/feature-flags/{key}", response_model=FeatureFlagResponse)
def update_feature_flag(
    org_id: UUID,
    key: str,
    payload: FeatureFlagUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeatureFlagResponse:
    require_org_role(org_id=org_id, user_id=current_user.id, db=db, minimum=RoleEnum.ADMIN)

    flag = db.query(FeatureFlag).filter(FeatureFlag.organization_id == org_id, FeatureFlag.key == key).one_or_none()
    if flag is None:
        flag = FeatureFlag(organization_id=org_id, key=key, enabled=payload.enabled)
        db.add(flag)
    else:
        flag.enabled = payload.enabled
    db.commit()

    return FeatureFlagResponse(key=flag.key, enabled=flag.enabled)
