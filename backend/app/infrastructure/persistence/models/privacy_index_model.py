from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class PrivacyIndexModel(Base):
    __tablename__ = "indice_privacidad"

    id_indice: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    nombre: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ruta_del_script: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    pruebas = relationship(
        "PrivacyIndexMastgTestModel",
        back_populates="indice_privacidad",
        cascade="all, delete-orphan",
    )