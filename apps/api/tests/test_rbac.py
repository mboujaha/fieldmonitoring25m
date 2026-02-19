from app.models import RoleEnum
from app.services.rbac import has_minimum_role


def test_rbac_role_hierarchy() -> None:
    assert has_minimum_role(RoleEnum.OWNER, RoleEnum.ADMIN)
    assert has_minimum_role(RoleEnum.ADMIN, RoleEnum.ANALYST)
    assert has_minimum_role(RoleEnum.ANALYST, RoleEnum.VIEWER)
    assert not has_minimum_role(RoleEnum.VIEWER, RoleEnum.ADMIN)
