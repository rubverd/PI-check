from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.security.mastg.base import MastgTestRunResult
from app.infrastructure.security.mastg.context import MastgAnalysisContext


LOGGING_MARKERS = [
    "android.util.Log",
    "Log.d",
    "Log.e",
    "Log.i",
    "Log.w",
    "Log.v",
    "System.out.print",
    "System.err.print",
    "printStackTrace",
]


class LoggingApisTest:
    id_prueba = "MASTG-TEST-0231"
    referencia_mastg = "MASTG-TEST-0231"
    nombre = "Logging APIs"
    descripcion = "Detecta referencias a APIs de logging potencialmente sensibles."
    owasp_category = "MASVS-CODE"

    def run(self, context: MastgAnalysisContext) -> MastgTestRunResult:
        matches = context.find_patterns(LOGGING_MARKERS, max_results=100)
        markers = sorted({match.value for match in matches})
        status = MastgResultStatus.FAIL if markers else MastgResultStatus.PASS
        return MastgTestRunResult(
            id_mastg=self.id_prueba,
            status=status,
            evidence={"markers": markers},
        )
