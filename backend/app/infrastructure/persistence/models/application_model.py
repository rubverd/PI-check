from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class ApplicationModel(Base):
    __tablename__ = "aplicacion"

    id_app: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    nombre: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    icono: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    categoria: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    desarrollador: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    modelo_integracion_actual: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="UNKNOWN",
    )

    versiones = relationship(
        "AppVersionModel",
        back_populates="aplicacion",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "modelo_integracion_actual IN ('HEALTH_CONNECT', 'LEGACY', 'UNKNOWN')",
            name="ck_aplicacion_modelo_integracion_actual",
        ),
    )