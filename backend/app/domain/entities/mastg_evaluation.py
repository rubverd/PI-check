from dataclasses import dataclass
from datetime import datetime

from app.domain.value_objects.mastg_result_status import MastgResultStatus


@dataclass
class MastgEvaluation:
    id_app: str
    version: str
    id_mastg: str

    resultado: MastgResultStatus = MastgResultStatus.NOT_EXECUTED
    ruta_resultado_json: str | None = None
    mensaje_error: str | None = None
    fecha_ejecucion: datetime | None = None