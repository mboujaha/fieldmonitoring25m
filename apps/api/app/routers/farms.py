from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, require_org_role
from app.db.session import get_db
from app.models import Farm, Membership, RoleEnum, User
from app.schemas import FarmCreateRequest, FarmResponse

router = APIRouter(prefix="/farms", tags=["farms"])


@router.post("", response_model=FarmResponse)
def create_farm(
    payload: FarmCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmResponse:
    org_id = UUID(payload.organization_id)
    require_org_role(org_id=org_id, user_id=current_user.id, db=db, minimum=RoleEnum.ADMIN)

    farm = Farm(
        organization_id=org_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(farm)
    db.commit()
    return FarmResponse(
        id=str(farm.id),
        organization_id=str(farm.organization_id),
        name=farm.name,
        description=farm.description,
        created_at=farm.created_at,
    )


@router.get("", response_model=list[FarmResponse])
def list_farms(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[FarmResponse]:
    org_ids = select(Membership.organization_id).where(Membership.user_id == current_user.id)
    farms = db.query(Farm).filter(Farm.organization_id.in_(org_ids)).order_by(Farm.created_at.desc()).all()

    return [
        FarmResponse(
            id=str(farm.id),
            organization_id=str(farm.organization_id),
            name=farm.name,
            description=farm.description,
            created_at=farm.created_at,
        )
        for farm in farms
    ]
