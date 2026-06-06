from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.mastg_test import MastgTest
from app.infrastructure.persistence.models.mastg_test_model import MastgTestModel


class MastgTestRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, id_mastg: str) -> MastgTest | None:
        model = self.db.get(MastgTestModel, id_mastg)
        return self._to_domain(model) if model else None

    def list_all(self) -> list[MastgTest]:
        stmt = select(MastgTestModel).order_by(MastgTestModel.id_mastg.asc())
        return [self._to_domain(model) for model in self.db.execute(stmt).scalars().all()]

    def save(self, test: MastgTest) -> MastgTest:
        existing = self.db.get(MastgTestModel, test.id_mastg)
        if existing is None:
            model = self._to_model(test)
            self.db.add(model)
            self.db.flush()
            return self._to_domain(model)

        existing.nombre = test.nombre
        existing.referencia_script_implementacion = test.referencia_script_implementacion
        existing.categoria_masvs = test.categoria_masvs
        existing.perfil = test.perfil
        existing.referencia_mastg = test.referencia_mastg
        existing.descripcion = test.descripcion
        existing.owasp_category = test.owasp_category
        self.db.flush()
        return self._to_domain(existing)

    def delete(self, id_mastg: str) -> bool:
        model = self.db.get(MastgTestModel, id_mastg)
        if model is None:
            return False
        self.db.delete(model)
        self.db.flush()
        return True

    def _to_domain(self, model: MastgTestModel) -> MastgTest:
        return MastgTest(
            id_mastg=model.id_mastg,
            nombre=model.nombre,
            referencia_script_implementacion=model.referencia_script_implementacion,
            categoria_masvs=model.categoria_masvs,
            perfil=model.perfil,
            referencia_mastg=model.referencia_mastg,
            descripcion=model.descripcion,
            owasp_category=model.owasp_category,
        )

    def _to_model(self, test: MastgTest) -> MastgTestModel:
        return MastgTestModel(
            id_mastg=test.id_mastg,
            nombre=test.nombre,
            referencia_script_implementacion=test.referencia_script_implementacion,
            categoria_masvs=test.categoria_masvs,
            perfil=test.perfil,
            referencia_mastg=test.referencia_mastg,
            descripcion=test.descripcion,
            owasp_category=test.owasp_category,
        )
