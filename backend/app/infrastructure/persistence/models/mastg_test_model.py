from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class MastgTestModel(Base):
    __tablename__ = "prueba_mastg"

    id_mastg: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    nombre: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    referencia_script_implementacion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    categoria_masvs: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    perfil: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    referencia_mastg: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    owasp_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    resultados = relationship(
        "MastgEvaluationModel",
        back_populates="prueba_mastg",
        cascade="all, delete-orphan",
    )

    indices = relationship(
        "PrivacyIndexMastgTestModel",
        back_populates="prueba_mastg",
        cascade="all, delete-orphan",
    )