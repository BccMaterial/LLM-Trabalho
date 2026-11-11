"""Create professionals table.

Revision ID: 20261111_01
Revises: 20261106_01
Create Date: 2026-11-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261111_01"
down_revision: Union[str, None] = "20261106_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "professionals",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("professionals")
