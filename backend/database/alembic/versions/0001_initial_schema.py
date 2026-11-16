"""Initial Olympics warehouse + Wikipedia crawl schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create all tables from SQLAlchemy metadata for Phase 1 bootstrap.
    from backend.database.base import Base
    import backend.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from backend.database.base import Base
    import backend.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
