from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.privacy_index import PrivacyIndex
from app.infrastructure.persistence.models.privacy_index_mastg_test_model import PrivacyIndexMastgTestModel
from app.infrastructure.persistence.models.privacy_index_model import PrivacyIndexModel


class PrivacyIndexRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, id_indice: str) -> PrivacyIndex | None:
        model = self.db.get(PrivacyIndexModel, id_indice)
        return self._to_domain(model) if model else None

    def list_all(self) -> list[PrivacyIndex]:
        stmt = select(PrivacyIndexModel).order_by(PrivacyIndexModel.id_indice.asc())
        return [self._to_domain(model) for model in self.db.execute(stmt).scalars().all()]

    def save(self, index: PrivacyIndex) -> PrivacyIndex:
        existing = self.db.get(PrivacyIndexModel, index.id_indice)
        if existing is None:
            model = PrivacyIndexModel(
                id_indice=index.id_indice,
                nombre=index.nombre,
                descripcion=index.descripcion,
                ruta_del_script=index.ruta_del_script,
            )
            self.db.add(model)
            self.db.flush()
            if index.pruebas_mastg:
                self.replace_tests(index.id_indice, index.pruebas_mastg)
            return self.find_by_id(index.id_indice) or index

        existing.nombre = index.nombre
        existing.descripcion = index.descripcion
        existing.ruta_del_script = index.ruta_del_script
        self.db.flush()
        if index.pruebas_mastg is not None:
            self.replace_tests(index.id_indice, index.pruebas_mastg)
        return self.find_by_id(index.id_indice) or index

    def delete(self, id_indice: str) -> bool:
        model = self.db.get(PrivacyIndexModel, id_indice)
        if model is None:
            return False
        self.db.delete(model)
        self.db.flush()
        return True

    def add_test(self, id_indice: str, id_mastg: str) -> None:
        existing = self.db.get(PrivacyIndexMastgTestModel, (id_indice, id_mastg))
        if existing is None:
            self.db.add(PrivacyIndexMastgTestModel(id_indice=id_indice, id_mastg=id_mastg))
            self.db.flush()

    def remove_test(self, id_indice: str, id_mastg: str) -> bool:
        model = self.db.get(PrivacyIndexMastgTestModel, (id_indice, id_mastg))
        if model is None:
            return False
        self.db.delete(model)
        self.db.flush()
        return True

    def list_test_ids(self, id_indice: str) -> list[str]:
        stmt = (
            select(PrivacyIndexMastgTestModel.id_mastg)
            .where(PrivacyIndexMastgTestModel.id_indice == id_indice)
            .order_by(PrivacyIndexMastgTestModel.id_mastg.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def replace_tests(self, id_indice: str, test_ids: list[str]) -> None:
        current = set(self.list_test_ids(id_indice))
        desired = set(test_ids)
        for id_mastg in current - desired:
            self.remove_test(id_indice, id_mastg)
        for id_mastg in desired - current:
            self.add_test(id_indice, id_mastg)

    def _to_domain(self, model: PrivacyIndexModel) -> PrivacyIndex:
        return PrivacyIndex(
            id_indice=model.id_indice,
            nombre=model.nombre,
            descripcion=model.descripcion,
            ruta_del_script=model.ruta_del_script,
            pruebas_mastg=self.list_test_ids(model.id_indice),
        )
