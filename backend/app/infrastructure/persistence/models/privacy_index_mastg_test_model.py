from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class PrivacyIndexMastgTestModel(Base):
    __tablename__ = "formar_parte"

    id_indice: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("indice_privacidad.id_indice", ondelete="CASCADE"),
        primary_key=True,
    )

    id_mastg: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("prueba_mastg.id_mastg", ondelete="CASCADE"),
        primary_key=True,
    )

    indice_privacidad = relationship(
        "PrivacyIndexModel",
        back_populates="pruebas",
    )

    prueba_mastg = relationship(
        "MastgTestModel",
        back_populates="indices",
    )