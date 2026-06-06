"""add ruta_apk to version_app

Revision ID: 8f3b7c2d4e91
Revises: 573ae4e32a05
Create Date: 2026-06-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8f3b7c2d4e91"
down_revision: Union[str, Sequence[str], None] = "573ae4e32a05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("version_app", sa.Column("ruta_apk", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("version_app", "ruta_apk")
