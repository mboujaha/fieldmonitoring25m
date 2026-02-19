"""initial schema

Revision ID: 20260219_0001
Revises:
Create Date: 2026-02-19 00:00:01
"""

from alembic import op

revision = "20260219_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    import os
    import sys

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    api_root = os.path.join(root, "apps", "api")
    if api_root not in sys.path:
        sys.path.insert(0, api_root)

    from app.db.session import Base
    from app.models import *  # noqa: F401,F403

    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    import os
    import sys

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    api_root = os.path.join(root, "apps", "api")
    if api_root not in sys.path:
        sys.path.insert(0, api_root)

    from app.db.session import Base
    from app.models import *  # noqa: F401,F403

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
