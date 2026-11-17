"""Add public identifiers to user sessions."""

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20261116_01"
down_revision: Union[str, None] = "20261114_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=True),
    )
    connection = op.get_bind()
    token_hashes = connection.execute(
        sa.text("SELECT token_hash FROM user_sessions")
    ).scalars()
    for token_hash in token_hashes:
        connection.execute(
            sa.text("UPDATE user_sessions SET id = :id WHERE token_hash = :token_hash"),
            {"id": uuid4(), "token_hash": token_hash},
        )

    with op.batch_alter_table("user_sessions") as batch:
        batch.alter_column(
            "id",
            existing_type=sa.Uuid(as_uuid=True),
            nullable=False,
        )
        batch.create_unique_constraint("uq_user_sessions_id", ["id"])


def downgrade() -> None:
    with op.batch_alter_table("user_sessions") as batch:
        batch.drop_constraint("uq_user_sessions_id", type_="unique")
        batch.drop_column("id")
