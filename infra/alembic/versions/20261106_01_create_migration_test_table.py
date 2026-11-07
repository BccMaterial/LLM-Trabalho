"""Create a simple table to verify database migrations.

Revision ID: 20261106_01
Revises:
Create Date: 2026-11-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "migration_test",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message", sa.String(length=100), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("migration_test")
