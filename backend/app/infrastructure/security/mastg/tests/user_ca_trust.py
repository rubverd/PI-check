from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.security.mastg.base import MastgTestRunResult
from app.infrastructure.security.mastg.context import MastgAnalysisContext


class UserCaTrustTest:
    id_prueba = "MASTG-TEST-0286"
    referencia_mastg = "MASTG-TEST-0286"
    nombre = "Trust in User-Provided CAs"
    descripcion = "Detecta confianza en certificados de CAs instaladas por el usuario."
    owasp_category = "MASVS-NETWORK"

    def run(self, context: MastgAnalysisContext) -> MastgTestRunResult:
        matches = context.find_regex(
            r"<\s*certificates[^>]+src\s*=\s*['\"]user['\"]|certificates\s+src\s*=\s*user|src\s*=\s*user",
            max_results=50,
        )
        status = MastgResultStatus.FAIL if matches else MastgResultStatus.PASS
        return MastgTestRunResult(
            id_mastg=self.id_prueba,
            status=status,
            evidence={"occurrences": [{"source": m.source, "value": m.value} for m in matches]},
        )
