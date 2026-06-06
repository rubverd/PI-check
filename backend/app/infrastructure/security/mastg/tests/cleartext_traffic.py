from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.security.mastg.base import MastgTestRunResult
from app.infrastructure.security.mastg.context import MastgAnalysisContext


class CleartextTrafficTest:
    id_prueba = "MASTG-TEST-0235"
    referencia_mastg = "MASTG-TEST-0235"
    nombre = "Cleartext Traffic"
    descripcion = "Detecta usos explícitos de tráfico HTTP en claro."
    owasp_category = "MASVS-NETWORK"

    def run(self, context: MastgAnalysisContext) -> MastgTestRunResult:
        matches = context.find_patterns([
            'usesCleartextTraffic="true"',
            "usesCleartextTraffic=true",
            "cleartextTrafficPermitted=\"true\"",
            'cleartextTrafficPermitted="true"',
            "cleartextTrafficPermitted=true",
        ], max_results=50)
        status = MastgResultStatus.FAIL if matches else MastgResultStatus.PASS
        return MastgTestRunResult(
            id_mastg=self.id_prueba,
            status=status,
            evidence={"occurrences": [{"source": m.source, "value": m.value} for m in matches]},
        )
