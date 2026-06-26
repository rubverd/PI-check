"""extend mastg evaluation engine

Revision ID: 9206e68d65e1
Revises: 8f3b7c2d4e91
Create Date: 2026-06-26 00:13:00.661413

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9206e68d65e1'
down_revision: Union[str, Sequence[str], None] = '8f3b7c2d4e91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prueba_mastg",
        sa.Column("descripcion", sa.Text(), nullable=True),
    )
    op.add_column(
        "prueba_mastg",
        sa.Column("origen", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "prueba_mastg",
        sa.Column("tipo_relacion", sa.String(length=50), nullable=True),
    )

    op.drop_constraint("ck_evaluar_resultado", "evaluar", type_="check")
    op.create_check_constraint(
        "ck_evaluar_resultado",
        "evaluar",
        "resultado IN ('PASS', 'FAIL', 'REVIEW', 'ERROR', 'NOT_EVALUABLE', 'NOT_APPLICABLE', 'NOT_EXECUTED')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_evaluar_resultado", "evaluar", type_="check")
    op.create_check_constraint(
        "ck_evaluar_resultado",
        "evaluar",
        "resultado IN ('PASS', 'FAIL', 'ERROR', 'NOT_APPLICABLE', 'NOT_EXECUTED')",
    )

    op.drop_column("prueba_mastg", "tipo_relacion")
    op.drop_column("prueba_mastg", "origen")
    op.drop_column("prueba_mastg", "descripcion")

