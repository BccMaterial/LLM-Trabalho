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
    dialect = op.get_bind().dialect.name
    uuid_default = (
        "gen_random_uuid()"
        if dialect == "postgresql"
        else (
            "lower(hex(randomblob(4)) || hex(randomblob(2)) || '4' || "
            "substr(hex(randomblob(2)), 2) || "
            "substr('89ab', abs(random()) % 4 + 1, 1) || "
            "substr(hex(randomblob(2)), 2) || hex(randomblob(6)))"
        )
    )
    op.create_table(
        "professionals",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text(uuid_default),
        ),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("professionals")
