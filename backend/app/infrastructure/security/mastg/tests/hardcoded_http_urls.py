from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.security.mastg.base import MastgTestRunResult
from app.infrastructure.security.mastg.context import MastgAnalysisContext


class HardcodedHttpUrlsTest:
    id_prueba = "MASTG-TEST-0233"
    referencia_mastg = "MASTG-TEST-0233"
    nombre = "Hardcoded HTTP URLs"
    descripcion = "Busca URLs http:// hardcodeadas en el artefacto Android."
    owasp_category = "MASVS-NETWORK"

    def run(self, context: MastgAnalysisContext) -> MastgTestRunResult:
        urls = context.find_http_urls(max_results=20)
        status = MastgResultStatus.FAIL if urls else MastgResultStatus.PASS
        return MastgTestRunResult(
            id_mastg=self.id_prueba,
            status=status,
            evidence={"urls": urls, "max_results": 20},
        )
