from sqlalchemy.orm import Session

from app.domain.entities.application import Application
from app.domain.value_objects.integration_model import IntegrationModel
from app.infrastructure.persistence.models.application_model import ApplicationModel


class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_id(self, id_app: str) -> Application | None:
        model = self.db.get(ApplicationModel, id_app)

        if model is None:
            return None

        return self._to_domain(model)

    def exists(self, id_app: str) -> bool:
        return self.db.get(ApplicationModel, id_app) is not None

    def save(self, application: Application) -> Application:
        existing = self.db.get(ApplicationModel, application.id_app)

        if existing is None:
            model = self._to_model(application)
            self.db.add(model)
            self.db.flush()
            return self._to_domain(model)

        existing.nombre = application.nombre
        existing.icono = application.icono
        existing.categoria = application.categoria
        existing.desarrollador = application.desarrollador
        existing.modelo_integracion_actual = application.modelo_integracion_actual.value

        self.db.flush()

        return self._to_domain(existing)

    def _to_domain(self, model: ApplicationModel) -> Application:
        return Application(
            id_app=model.id_app,
            nombre=model.nombre,
            icono=model.icono,
            categoria=model.categoria,
            desarrollador=model.desarrollador,
            modelo_integracion_actual=IntegrationModel(model.modelo_integracion_actual),
        )

    def _to_model(self, application: Application) -> ApplicationModel:
        return ApplicationModel(
            id_app=application.id_app,
            nombre=application.nombre,
            icono=application.icono,
            categoria=application.categoria,
            desarrollador=application.desarrollador,
            modelo_integracion_actual=application.modelo_integracion_actual.value,
        )