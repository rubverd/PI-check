from __future__ import annotations

import cmd
import os
import shlex
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.database.session import SessionLocal


class AdminConsole(cmd.Cmd):
    intro = (
        "Consola administrativa de PI-check. Escribe 'help' para ver comandos "
        "disponibles o 'exit' para salir."
    )
    prompt = "pi-check-admin> "

    def __init__(self, db: Session, *, debug: bool = False) -> None:
        super().__init__()
        self.db = db
        self.debug = debug

    def do_exit(self, arg: str) -> bool:
        """Salir de la consola."""
        print("Cerrando consola administrativa.")
        return True

    def do_quit(self, arg: str) -> bool:
        """Alias de exit."""
        return self.do_exit(arg)

    def do_EOF(self, arg: str) -> bool:  # noqa: N802 - cmd.Cmd usa este nombre.
        """Salir con Ctrl-D."""
        print()
        return self.do_exit(arg)

    def do_help(self, arg: str) -> None:
        """Mostrar ayuda de comandos."""
        if arg.strip():
            return super().do_help(arg)
        print(
            """
Comandos disponibles:
  help
  exit

  apps list
      Lista id_app, nombre y modelo_integracion_actual.

  versions list <id_app>
      Lista version, version_code, modelo_integracion, estado_mobsf y ruta_apk.

  apk register <ruta_apk> [--run-mobsf]
      Registra un APK local existente en el contenedor. Opcionalmente lanza MobSF.

  mastg tests
      Lista pruebas MASTG disponibles.

  mastg indexes
      Lista índices de privacidad y número de pruebas.

  mastg index show <id_indice>
      Muestra información del índice y sus pruebas asociadas.

  mastg index create
      Crea un índice MASTG personalizado en modo asistente.

  mastg evaluate <id_app> <version> <id_indice>
      Ejecuta una evaluación MASTG manual para app/version/index.
""".strip()
        )

    def default(self, line: str) -> None:
        print(f"Comando no reconocido: {line}")
        print("Escribe 'help' para ver los comandos disponibles.")

    def emptyline(self) -> None:
        return None

    def do_apps(self, arg: str) -> None:
        parts = self._split_args(arg)
        if parts != ["list"]:
            print("Uso: apps list")
            return
        self._run_readonly(self._apps_list)

    def do_versions(self, arg: str) -> None:
        parts = self._split_args(arg)
        if len(parts) != 2 or parts[0] != "list":
            print("Uso: versions list <id_app>")
            return
        self._run_readonly(lambda: self._versions_list(parts[1]))

    def do_apk(self, arg: str) -> None:
        parts = self._split_args(arg)
        if len(parts) not in (2, 3) or parts[:1] != ["register"]:
            print("Uso: apk register <ruta_apk> [--run-mobsf]")
            return
        run_mobsf = False
        if len(parts) == 3:
            if parts[2] != "--run-mobsf":
                print("Uso: apk register <ruta_apk> [--run-mobsf]")
                return
            run_mobsf = True
        self._apk_register(parts[1], run_mobsf=run_mobsf)

    def do_mastg(self, arg: str) -> None:
        parts = self._split_args(arg)
        if parts == ["tests"]:
            self._run_readonly(self._mastg_tests)
        elif parts == ["indexes"]:
            self._run_readonly(self._mastg_indexes)
        elif len(parts) == 3 and parts[:2] == ["index", "show"]:
            self._run_readonly(lambda: self._mastg_index_show(parts[2]))
        elif parts == ["index", "create"]:
            self._mastg_index_create()
        elif len(parts) == 4 and parts[0] == "evaluate":
            self._mastg_evaluate(id_app=parts[1], version=parts[2], index_id=parts[3])
        else:
            print(
                "Uso: mastg tests | mastg indexes | mastg index show <id_indice> | "
                "mastg index create | mastg evaluate <id_app> <version> <id_indice>"
            )

    def _apps_list(self) -> None:
        rows = self.db.execute(text("""
            SELECT id_app, nombre, modelo_integracion_actual
            FROM aplicacion
            ORDER BY id_app
        """)).mappings().all()
        self._print_rows(rows, ["id_app", "nombre", "modelo_integracion_actual"])

    def _versions_list(self, id_app: str) -> None:
        rows = self.db.execute(text("""
            SELECT version, version_code, modelo_integracion, estado_mobsf, ruta_apk
            FROM version_app
            WHERE id_app = :id_app
            ORDER BY version
        """), {"id_app": id_app}).mappings().all()
        self._print_rows(
            rows,
            ["version", "version_code", "modelo_integracion", "estado_mobsf", "ruta_apk"],
        )

    def _apk_register(self, apk_path: str, *, run_mobsf: bool) -> None:
        path = Path(apk_path)
        if not path.exists():
            print(f"Error: la ruta no existe dentro del contenedor: {apk_path}")
            return
        try:
            from app.application.services.app_registration_service import AppRegistrationService

            service = AppRegistrationService(self.db)
            prepared = service.register_local_apk(
                apk_path=apk_path,
                source_label="admin_console",
            )
            self.db.commit()
            messages = list(prepared.messages)
            if run_mobsf:
                from app.application.services.app_analysis_service import AppAnalysisService

                report, analysis_messages = AppAnalysisService(
                    self.db
                ).ensure_mobsf_reports([prepared])[0]
                prepared.app_version = report.version_app
                messages.extend(analysis_messages)
            else:
                messages.append(
                    "[MOBSF] No se lanza MobSF porque --run-mobsf no fue indicado."
                )

            for message in messages:
                print(message)
            app = prepared.application
            version = prepared.app_version
            self._print_rows(
                [
                    {
                        "id_app": app.id_app,
                        "nombre": app.nombre,
                        "version": version.version,
                        "modelo_integracion": _value(version.modelo_integracion),
                        "ruta_apk": version.ruta_apk,
                        "estado_mobsf": _value(version.estado_mobsf),
                    }
                ],
                [
                    "id_app",
                    "nombre",
                    "version",
                    "modelo_integracion",
                    "ruta_apk",
                    "estado_mobsf",
                ],
            )
        except Exception as exc:
            self.db.rollback()
            self._print_error(exc)

    def _mastg_tests(self) -> None:
        rows = self.db.execute(text("""
            SELECT id_mastg, nombre, categoria_masvs, origen, referencia_script_implementacion
            FROM prueba_mastg
            ORDER BY id_mastg
        """)).mappings().all()
        self._print_rows(
            rows,
            [
                "id_mastg",
                "nombre",
                "categoria_masvs",
                "origen",
                "referencia_script_implementacion",
            ],
        )

    def _mastg_indexes(self) -> None:
        from app.application.services.mastg.mastg_evaluation_service import MastgEvaluationService

        rows = MastgEvaluationService(self.db).list_indexes()
        self._print_rows(rows, ["id_indice", "nombre", "descripcion", "total_pruebas"])

    def _mastg_index_show(self, index_id: str) -> None:
        index = self.db.execute(text("""
            SELECT i.id_indice, i.nombre, i.descripcion, i.ruta_del_script, COUNT(fp.id_mastg) AS total_pruebas
            FROM indice_privacidad i
            LEFT JOIN formar_parte fp ON fp.id_indice = i.id_indice
            WHERE i.id_indice = :index_id
            GROUP BY i.id_indice, i.nombre, i.descripcion, i.ruta_del_script
        """), {"index_id": index_id}).mappings().first()
        if index is None:
            print(f"No existe el índice: {index_id}")
            return
        print("Índice:")
        self._print_rows(
            [index],
            ["id_indice", "nombre", "descripcion", "ruta_del_script", "total_pruebas"],
        )
        rows = self._tests_for_index(index_id)
        print("Pruebas del índice:")
        self._print_rows(
            rows,
            [
                "id_mastg",
                "nombre",
                "categoria_masvs",
                "origen",
                "referencia_script_implementacion",
            ],
        )

    def _mastg_index_create(self) -> None:
        try:
            index_id = input("id_indice: ").strip()
            name = input("nombre: ").strip()
            description = input("descripción: ").strip()
            if not index_id or not name:
                print("Error: id_indice y nombre son obligatorios.")
                return
            tests = self._all_mastg_tests()
            if not tests:
                print("No hay pruebas MASTG disponibles.")
                return
            print("Pruebas disponibles:")
            numbered = {
                str(pos): row["id_mastg"] for pos, row in enumerate(tests, start=1)
            }
            for pos, row in enumerate(tests, start=1):
                print(f"  {pos}. {row['id_mastg']} - {row['nombre']}")
            selected_raw = input("IDs o números separados por coma: ").strip()
            selected_ids = self._parse_selected_tests(
                selected_raw,
                numbered,
                {row["id_mastg"] for row in tests},
            )
            if not selected_ids:
                print("Error: debes seleccionar al menos una prueba válida.")
                return
            if self.db.execute(
                text("SELECT 1 FROM indice_privacidad WHERE id_indice = :id"),
                {"id": index_id},
            ).first():
                print(f"Error: ya existe un índice con id_indice={index_id!r}.")
                return
            self.db.execute(text("""
                INSERT INTO indice_privacidad (id_indice, nombre, descripcion, ruta_del_script)
                VALUES (:id_indice, :nombre, :descripcion, NULL)
            """), {"id_indice": index_id, "nombre": name, "descripcion": description or None})
            for test_id in selected_ids:
                self.db.execute(text("""
                    INSERT INTO formar_parte (id_indice, id_mastg)
                    VALUES (:id_indice, :id_mastg)
                    ON CONFLICT DO NOTHING
                """), {"id_indice": index_id, "id_mastg": test_id})
            self.db.commit()
            print(f"Índice creado correctamente: {index_id} ({len(selected_ids)} pruebas).")
        except Exception as exc:
            self.db.rollback()
            self._print_error(exc)

    def _mastg_evaluate(self, *, id_app: str, version: str, index_id: str) -> None:
        try:
            from app.application.services.mastg.mastg_evaluation_service import MastgEvaluationService

            result = MastgEvaluationService(self.db).evaluate_version(
                index_id=index_id,
                id_app=id_app,
                version=version,
            )
            score = result.get("score") or {}
            print("Evaluación MASTG finalizada.")
            print(f"Score: {score.get('score')} ({score.get('score_percent')}%)")
            print(f"Coverage: {score.get('coverage')} ({score.get('coverage_percent')}%)")
            print(
                f"Pruebas evaluadas: {score.get('total_tests')} "
                f"(puntuables: {score.get('scorable_tests')})"
            )
            counts = Counter(item.get("resultado") for item in result.get("results", []))
            print("Resumen por estados:")
            for state, count in sorted(counts.items()):
                print(f"  {state}: {count}")
        except Exception as exc:
            self.db.rollback()
            self._print_error(exc)

    def _tests_for_index(self, index_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute(text("""
            SELECT pm.id_mastg, pm.nombre, pm.categoria_masvs, pm.origen, pm.referencia_script_implementacion
            FROM formar_parte fp
            JOIN prueba_mastg pm ON pm.id_mastg = fp.id_mastg
            WHERE fp.id_indice = :index_id
            ORDER BY pm.id_mastg
        """), {"index_id": index_id}).mappings().all()]

    def _all_mastg_tests(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute(text("""
            SELECT id_mastg, nombre
            FROM prueba_mastg
            ORDER BY id_mastg
        """)).mappings().all()]

    def _parse_selected_tests(
        self,
        raw: str,
        numbered: dict[str, str],
        valid_ids: set[str],
    ) -> list[str]:
        selected: list[str] = []
        invalid: list[str] = []
        for token in [part.strip() for part in raw.split(",") if part.strip()]:
            test_id = numbered.get(token, token)
            if test_id not in valid_ids:
                invalid.append(token)
                continue
            if test_id not in selected:
                selected.append(test_id)
        if invalid:
            raise ValueError("Pruebas no válidas: " + ", ".join(invalid))
        return selected

    def _run_readonly(self, action) -> None:
        try:
            action()
        except Exception as exc:
            self.db.rollback()
            self._print_error(exc)

    def _split_args(self, arg: str) -> list[str]:
        try:
            return shlex.split(arg)
        except ValueError as exc:
            print(f"Error parseando argumentos: {exc}")
            return []

    def _print_error(self, exc: Exception) -> None:
        print(f"Error: {exc}")
        if self.debug:
            traceback.print_exc()

    @staticmethod
    def _print_rows(rows: Iterable[Any], columns: list[str]) -> None:
        materialized = [dict(row) for row in rows]
        if not materialized:
            print("Sin resultados.")
            return
        widths = {col: len(col) for col in columns}
        for row in materialized:
            for col in columns:
                widths[col] = max(widths[col], len(str(row.get(col) or "")))
        header = " | ".join(col.ljust(widths[col]) for col in columns)
        sep = "-+-".join("-" * widths[col] for col in columns)
        print(header)
        print(sep)
        for row in materialized:
            print(
                " | ".join(
                    str(row.get(col) or "").ljust(widths[col]) for col in columns
                )
            )


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def main() -> int:
    debug = os.getenv("PI_CHECK_ADMIN_DEBUG", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    db = SessionLocal()
    try:
        AdminConsole(db, debug=debug).cmdloop()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
