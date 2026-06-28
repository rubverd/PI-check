from __future__ import annotations

from app.application.services.mastg.evaluators.base import (
    iter_strings,
    limit_evidence,
    walk_items,
)
from app.application.services.mastg.models import MastgEvaluationContext, MastgRuleResult


ALLOW_BACKUP_KEYS = {
    "allowbackup",
    "allow_backup",
    "android:allowbackup",
}

BACKUP_RULE_KEYS = {
    "fullbackupcontent",
    "full_backup_content",
    "dataextractionrules",
    "data_extraction_rules",
    "android:fullbackupcontent",
    "android:dataextractionrules",
}

BACKUP_TRUE_TEXT_PATTERNS = (
    "android:allowbackup=\"true\"",
    "allowbackup=true",
    "allow backup true",
    "allowbackup: true",
)

BACKUP_FALSE_TEXT_PATTERNS = (
    "android:allowbackup=\"false\"",
    "allowbackup=false",
    "allow backup false",
    "allowbackup: false",
)


def _normalize_key(key: object) -> str:
    return str(key).replace("-", "_").replace(" ", "_").replace(":", "").lower()


def _collect_backup_evidence(mobsf_json: dict) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    allow_backup_true: list[dict[str, object]] = []
    allow_backup_false: list[dict[str, object]] = []
    backup_rules: list[dict[str, object]] = []

    for key, value in walk_items(mobsf_json):
        normalized_key = _normalize_key(key)

        if normalized_key in ALLOW_BACKUP_KEYS:
            if value is True:
                allow_backup_true.append({"source": "json_key", "key": key, "value": value})
            elif value is False:
                allow_backup_false.append({"source": "json_key", "key": key, "value": value})
            elif isinstance(value, str):
                normalized_value = value.strip().lower()

                if normalized_value in {"true", "yes", "enabled", "1"}:
                    allow_backup_true.append({"source": "json_key", "key": key, "value": value})
                elif normalized_value in {"false", "no", "disabled", "0"}:
                    allow_backup_false.append({"source": "json_key", "key": key, "value": value})

        if normalized_key in BACKUP_RULE_KEYS:
            backup_rules.append({"source": "json_key", "key": key, "value": value})

    for text in iter_strings(mobsf_json):
        normalized_text = text.replace(" ", "").lower()

        if any(pattern.replace(" ", "") in normalized_text for pattern in BACKUP_TRUE_TEXT_PATTERNS):
            allow_backup_true.append({"source": "json_text", "text": text[:500]})

        if any(pattern.replace(" ", "") in normalized_text for pattern in BACKUP_FALSE_TEXT_PATTERNS):
            allow_backup_false.append({"source": "json_text", "text": text[:500]})

        lowered = text.lower()
        if "dataextractionrules" in lowered or "fullbackupcontent" in lowered:
            backup_rules.append({"source": "json_text", "text": text[:500]})

    return allow_backup_true, allow_backup_false, backup_rules


def evaluate(context: MastgEvaluationContext) -> MastgRuleResult:
    if not context.has_mobsf_json:
        return MastgRuleResult.not_evaluable(
            "No hay informe MobSF JSON disponible para evaluar configuración de backup."
        )

    mobsf_json = context.mobsf_json or {}

    allow_backup_true, allow_backup_false, backup_rules = _collect_backup_evidence(mobsf_json)

    details = {
        "allow_backup_true_count": len(allow_backup_true),
        "allow_backup_false_count": len(allow_backup_false),
        "backup_rules_count": len(backup_rules),
    }

    evidence = limit_evidence(
        [
            {
                "type": "allow_backup_true",
                **item,
            }
            for item in allow_backup_true
        ]
        + [
            {
                "type": "allow_backup_false",
                **item,
            }
            for item in allow_backup_false
        ]
        + [
            {
                "type": "backup_rule",
                **item,
            }
            for item in backup_rules
        ]
    )

    if allow_backup_true:
        if backup_rules:
            return MastgRuleResult.review(
                "La aplicación permite backup y declara reglas de backup/extracción; requiere revisar si excluyen datos sensibles.",
                details=details,
                evidence=evidence,
                recommendation=(
                    "Verificar que las reglas de backup excluyen credenciales, tokens, historiales, "
                    "datos personales y datos de salud."
                ),
            )

        return MastgRuleResult.review(
            "La aplicación permite backup y no se han identificado reglas restrictivas claras en el informe MobSF.",
            details=details,
            evidence=evidence,
            recommendation=(
                "Deshabilitar backup o definir reglas explícitas de exclusión para datos sensibles."
            ),
        )

    if allow_backup_false:
        return MastgRuleResult.pass_(
            "La aplicación declara backup deshabilitado.",
            details=details,
            evidence=evidence,
        )

    return MastgRuleResult.not_evaluable(
        "No se han encontrado evidencias suficientes sobre allowBackup o reglas de backup en el informe MobSF."
    )