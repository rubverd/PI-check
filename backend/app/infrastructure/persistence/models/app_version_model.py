from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class AppVersionModel(Base):
    __tablename__ = "version_app"

    id_app: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("aplicacion.id_app", ondelete="CASCADE"),
        primary_key=True,
    )

    version: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    version_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    fecha_version: Mapped[date | None] = mapped_column(
        nullable=True,
    )

    categoria: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    modelo_integracion: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="UNKNOWN",
    )

    ruta_informe_mobsf: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    hash_mobsf: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    apk_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    ruta_apk: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    estado_mobsf: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="NOT_ANALYZED",
    )

    aplicacion = relationship(
        "ApplicationModel",
        back_populates="versiones",
    )

    resultados_mastg = relationship(
        "MastgEvaluationModel",
        back_populates="version_app",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "modelo_integracion IN ('HEALTH_CONNECT', 'LEGACY', 'UNKNOWN')",
            name="ck_version_app_modelo_integracion",
        ),
        CheckConstraint(
            "estado_mobsf IN ('NOT_ANALYZED', 'PENDING', 'SUCCESS', 'ERROR')",
            name="ck_version_app_estado_mobsf",
        ),
    )
