from dataclasses import dataclass

from app.domain.value_objects.integration_model import IntegrationModel


@dataclass
class Application:
    id_app: str
    nombre: str
    icono: str | None = None
    categoria: str | None = None
    desarrollador: str | None = None
    modelo_integracion_actual: IntegrationModel = IntegrationModel.UNKNOWN