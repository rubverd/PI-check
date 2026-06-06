"""add mastg lite catalog metadata

Revision ID: 94d9c6b6d1f2
Revises: 573ae4e32a05
Create Date: 2026-06-02 04:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "94d9c6b6d1f2"
down_revision: Union[str, Sequence[str], None] = "573ae4e32a05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("prueba_mastg", sa.Column("referencia_mastg", sa.String(length=100), nullable=True))
    op.add_column("prueba_mastg", sa.Column("descripcion", sa.Text(), nullable=True))
    op.add_column("prueba_mastg", sa.Column("owasp_category", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("prueba_mastg", "owasp_category")
    op.drop_column("prueba_mastg", "descripcion")
    op.drop_column("prueba_mastg", "referencia_mastg")
