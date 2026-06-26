from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class MastgEvaluationModel(Base):
    __tablename__ = "evaluar"

    id_app: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    version: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    id_mastg: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("prueba_mastg.id_mastg", ondelete="CASCADE"),
        primary_key=True,
    )

    resultado: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="NOT_EXECUTED",
    )

    ruta_resultado_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    mensaje_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    fecha_ejecucion: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    version_app = relationship(
        "AppVersionModel",
        back_populates="resultados_mastg",
    )

    prueba_mastg = relationship(
        "MastgTestModel",
        back_populates="resultados",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["id_app", "version"],
            ["version_app.id_app", "version_app.version"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "resultado IN ('PASS', 'FAIL', 'REVIEW', 'ERROR', 'NOT_EVALUABLE', 'NOT_APPLICABLE', 'NOT_EXECUTED')",
            name="ck_evaluar_resultado",
        ),
    )