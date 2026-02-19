import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import Membership, RoleEnum, User
from app.services.rbac import has_minimum_role

bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Missing subject")
        user = db.get(User, uuid.UUID(user_id))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
    return user


def require_org_role(org_id: uuid.UUID, user_id: uuid.UUID, db: Session, minimum: RoleEnum = RoleEnum.VIEWER) -> Membership:
    membership = (
        db.query(Membership)
        .filter(Membership.organization_id == org_id, Membership.user_id == user_id)
        .one_or_none()
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing organization membership")

    if not has_minimum_role(actual=membership.role, minimum=minimum):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return membership
