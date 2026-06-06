from app.domain.value_objects.mastg_result_status import MastgResultStatus
from app.infrastructure.security.mastg.base import MastgTestRunResult
from app.infrastructure.security.mastg.context import MastgAnalysisContext


class BackupConfigTest:
    id_prueba = "MASTG-TEST-0262"
    referencia_mastg = "MASTG-TEST-0262"
    nombre = "Backup Configurations Not Excluding Sensitive Data"
    descripcion = "Busca allowBackup y reglas de backup/data extraction poco restrictivas."
    owasp_category = "MASVS-STORAGE"

    def run(self, context: MastgAnalysisContext) -> MastgTestRunResult:
        allow_backup_true = context.find_patterns([
            'android:allowBackup="true"',
            "allowBackup=true",
            "allowBackup\u0000\u0001",
        ], max_results=20)
        allow_backup_false = context.find_patterns([
            'android:allowBackup="false"',
            "allowBackup=false",
        ], max_results=20)
        rules = context.find_patterns([
            "fullBackupContent",
            "dataExtractionRules",
            "backup_rules",
            "data_extraction_rules",
            "<exclude",
        ], max_results=50)

        fail = bool(allow_backup_true) and not bool(rules)
        status = MastgResultStatus.FAIL if fail else MastgResultStatus.PASS
        return MastgTestRunResult(
            id_mastg=self.id_prueba,
            status=status,
            evidence={
                "allow_backup_true": [match.source for match in allow_backup_true],
                "allow_backup_false": [match.source for match in allow_backup_false],
                "backup_rules_markers": [match.value for match in rules],
                "heuristic": "FAIL si allowBackup=true aparece sin marcadores de reglas restrictivas.",
            },
        )
