from app.models import RoleEnum

ROLE_ORDER = {
    RoleEnum.VIEWER: 0,
    RoleEnum.ANALYST: 1,
    RoleEnum.ADMIN: 2,
    RoleEnum.OWNER: 3,
}


def has_minimum_role(actual: RoleEnum, minimum: RoleEnum) -> bool:
    return ROLE_ORDER[actual] >= ROLE_ORDER[minimum]
