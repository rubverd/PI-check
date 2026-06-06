from dataclasses import dataclass
from datetime import date

from app.domain.value_objects.integration_model import IntegrationModel
from app.domain.value_objects.mobsf_analysis_status import MobSFAnalysisStatus


@dataclass
class AppVersion:
    id_app: str
    version: str

    fecha_version: date | None = None
    categoria: str | None = None
    modelo_integracion: IntegrationModel = IntegrationModel.UNKNOWN

    version_code: int | None = None
    apk_sha256: str | None = None
    ruta_apk: str | None = None

    ruta_informe_mobsf: str | None = None
    hash_mobsf: str | None = None
    estado_mobsf: MobSFAnalysisStatus = MobSFAnalysisStatus.NOT_ANALYZED
