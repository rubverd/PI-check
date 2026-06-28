from __future__ import annotations

import cmd
import os
import shlex
import sys
import traceback
from pathlib import Path
from typing import Any, Iterable

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.database.session import SessionLocal

LONG_COLUMNS = {
    "ruta_apk",
    "ruta_informe_mobsf",
    "ruta_resultado_json",
    "referencia_script_implementacion",
    "icono",
    "descripcion",
    "summary",
}
STATUS_STYLES = {
    "PASS": "green",
    "FAIL": "red",
    "REVIEW": "yellow",
    "NOT_EVALUABLE": "blue",
    "NOT_EXECUTED": "dim",
    "ERROR": "bright_red",
}


class AdminConsole(cmd.Cmd):
    intro = None
    prompt = "pi-check-admin> "

    def __init__(self, db: Session, *, debug: bool = False) -> None:
        super().__init__()
        self.db = db
        self.debug = debug
        self.console = Console()

    def preloop(self) -> None:
        self.console.print(
            Panel.fit(
                "[bold cyan]PI-check Admin Console[/bold cyan]\n"
                "[white]Gestión de APKs, MobSF e índices[/white]",
                box=box.HEAVY,
                border_style="cyan",
            )
        )
        counters = self._load_banner_counters()
        if counters["connected"]:
            self.console.print("[green]Base de datos: conectada[/green]")
        else:
            self.console.print("[yellow]Base de datos: warning al consultar contadores[/yellow]")
        self.console.print(f"Aplicaciones registradas: {counters['apps']}")
        self.console.print(f"Pruebas MASTG: {counters['tests']}")
        self.console.print(f"Índices disponibles: {counters['indexes']}")
        if counters["warnings"]:
            for warning in counters["warnings"]:
                self.console.print(f"[yellow]Aviso: {warning}[/yellow]")
        self.console.print("\nEscribe [bold]help[/bold] para ver comandos disponibles.\n")

    def do_exit(self, arg: str) -> bool:
        """Salir de la consola."""
        self.console.print("[cyan]Cerrando consola administrativa.[/cyan]")
        return True

    def do_quit(self, arg: str) -> bool:
        """Alias de exit."""
        return self.do_exit(arg)

    def do_EOF(self, arg: str) -> bool:  # noqa: N802 - cmd.Cmd usa este nombre.
        """Salir con Ctrl-D."""
        self.console.print()
        return self.do_exit(arg)

    def do_clear(self, arg: str) -> None:
        """Limpiar pantalla."""
        try:
            if os.system("clear") != 0:
                self.console.print("\n" * 8)
        except Exception:
            self.console.print("\n" * 8)

    def do_help(self, arg: str) -> None:
        """Mostrar ayuda de comandos agrupada por secciones."""
        if arg.strip():
            return super().do_help(arg)
        help_text = """
[bold cyan]Sistema[/bold cyan]
  help
  clear
  exit
  quit

[bold cyan]Aplicaciones[/bold cyan]
  apps list
  apps show <id_app>
  versions list <id_app>

[bold cyan]APKs[/bold cyan]
  apk inspect <ruta_apk>
  apk register <ruta_apk> [--run-mobsf]

[bold cyan]MobSF[/bold cyan]
  mobsf health
  mobsf analyze <id_app> <version>

[bold cyan]MASTG[/bold cyan]
  mastg tests
  mastg tests list
  mastg tests show <id_mastg>
  mastg indexes
  mastg indexes list
  mastg index show <id_indice>
  mastg index create
  mastg index delete <id_indice>
  mastg evaluate <id_app> <version> <id_indice>
  mastg reevaluate all
""".strip()
        self.console.print(
            Panel(help_text, title="Ayuda", border_style="cyan", box=box.ROUNDED)
        )

    def default(self, line: str) -> None:
        self.console.print(f"[red]Comando no reconocido:[/red] {line}")
        self.console.print("Escribe [bold]help[/bold] para ver los comandos disponibles.")

    def emptyline(self) -> None:
        return None

    def do_apps(self, arg: str) -> None:
        parts = self._split_args(arg)
        if parts == ["list"]:
            self._run_readonly(self._apps_list)
        elif len(parts) == 2 and parts[0] == "show":
            self._run_readonly(lambda: self._apps_show(parts[1]))
        else:
            self.console.print("[yellow]Uso: apps list | apps show <id_app>[/yellow]")

    def do_versions(self, arg: str) -> None:
        parts = self._split_args(arg)
        if len(parts) != 2 or parts[0] != "list":
            self.console.print("[yellow]Uso: versions list <id_app>[/yellow]")
            return
        self._run_readonly(lambda: self._versions_list(parts[1]))

    def do_apk(self, arg: str) -> None:
        parts = self._split_args(arg)
        if len(parts) == 2 and parts[0] == "inspect":
            self._apk_inspect(parts[1])
            return
        if len(parts) in (2, 3) and parts[:1] == ["register"]:
            run_mobsf = False
            if len(parts) == 3:
                if parts[2] != "--run-mobsf":
                    self.console.print(
                        "[yellow]Uso: apk register <ruta_apk> [--run-mobsf][/yellow]"
                    )
                    return
                run_mobsf = True
            self._apk_register(parts[1], run_mobsf=run_mobsf)
            return
        self.console.print(
            "[yellow]Uso: apk inspect <ruta_apk> | "
            "apk register <ruta_apk> [--run-mobsf][/yellow]"
        )

    def do_mobsf(self, arg: str) -> None:
        parts = self._split_args(arg)
        if parts == ["health"]:
            self._mobsf_health()
        elif len(parts) == 3 and parts[0] == "analyze":
            self._mobsf_analyze(id_app=parts[1], version=parts[2])
        else:
            self.console.print(
                "[yellow]Uso: mobsf health | mobsf analyze <id_app> <version>[/yellow]"
            )

    def do_mastg(self, arg: str) -> None:
        parts = self._split_args(arg)
        if parts in (["tests"], ["tests", "list"]):
            self._run_readonly(self._mastg_tests)
        elif len(parts) == 3 and parts[:2] == ["tests", "show"]:
            self._run_readonly(lambda: self._mastg_test_show(parts[2]))
        elif parts in (["indexes"], ["indexes", "list"]):
            self._run_readonly(self._mastg_indexes)
        elif len(parts) == 3 and parts[:2] == ["index", "show"]:
            self._run_readonly(lambda: self._mastg_index_show(parts[2]))
        elif parts == ["index", "create"]:
            self._mastg_index_create()
        elif len(parts) == 3 and parts[:2] == ["index", "delete"]:
            self._mastg_index_delete(parts[2])
        elif len(parts) == 4 and parts[0] == "evaluate":
            self._mastg_evaluate(id_app=parts[1], version=parts[2], index_id=parts[3])
        elif parts == ["reevaluate", "all"]:
            self._mastg_reevaluate_all()
        else:
            self.console.print(
                "[yellow]Uso: mastg tests [list] | mastg tests show <id_mastg> | "
                "mastg indexes [list] | mastg index show/create/delete <id_indice> | "
                "mastg evaluate <id_app> <version> <id_indice> | "
                "mastg reevaluate all[/yellow]"
            )

    def _apps_list(self) -> None:
        rows = self.db.execute(text("""
            SELECT id_app, nombre, modelo_integracion_actual
            FROM aplicacion
            ORDER BY id_app
        """)).mappings().all()
        self._print_rows(
            rows,
            ["id_app", "nombre", "modelo_integracion_actual"],
            title="Aplicaciones registradas",
        )

    def _apps_show(self, id_app: str) -> None:
        app = self.db.execute(text("""
            SELECT id_app, nombre, desarrollador, categoria, icono, modelo_integracion_actual
            FROM aplicacion
            WHERE id_app = :id_app
        """), {"id_app": id_app}).mappings().first()
        if app is None:
            self.console.print(f"[red]No existe la aplicación:[/red] {id_app}")
            return
        versions_count = self.db.execute(text("""
            SELECT COUNT(*) FROM version_app WHERE id_app = :id_app
        """), {"id_app": id_app}).scalar_one()
        mastg_summary = self.db.execute(text("""
            SELECT resultado, COUNT(*) AS total
            FROM evaluar
            WHERE id_app = :id_app
            GROUP BY resultado
            ORDER BY resultado
        """), {"id_app": id_app}).mappings().all()
        self._print_rows(
            [app],
            ["id_app", "nombre", "desarrollador", "categoria", "icono", "modelo_integracion_actual"],
            title="Detalle de aplicación",
        )
        self.console.print(f"[bold]Versiones registradas:[/bold] {versions_count}")
        self._print_rows(
            mastg_summary,
            ["resultado", "total"],
            title="Resumen de resultados MASTG",
        )

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
            title=f"Versiones de {id_app}",
        )

    def _apk_inspect(self, apk_path: str) -> None:
        path = Path(apk_path)
        if not path.exists():
            self.console.print(f"[red]La ruta no existe dentro del contenedor:[/red] {apk_path}")
            return
        try:
            from app.infrastructure.external.apk_metadata_extractor import extract_apk_metadata

            metadata = extract_apk_metadata(
                apk_path=path,
                fallback_app_id=f"manual.{path.stem}",
            )
            self.console.print(
                Panel(
                    "Inspección completada sin registrar filas en base de datos.\n"
                    "[yellow]Nota:[/yellow] el extractor puede generar/copiar iconos como efecto secundario.",
                    title="APK inspect",
                    border_style="cyan",
                )
            )
            self._print_rows(
                [
                    {
                        "id_app": metadata.id_app,
                        "nombre": metadata.app_label,
                        "version": metadata.version,
                        "version_code": metadata.version_code,
                        "apk_sha256": metadata.apk_sha256,
                        "modelo_integracion": _value(metadata.modelo_integracion),
                        "categoria": metadata.categoria,
                        "icono": metadata.icon,
                        "icon_source": getattr(metadata, "icon_source", None),
                    }
                ],
                [
                    "id_app",
                    "nombre",
                    "version",
                    "version_code",
                    "apk_sha256",
                    "modelo_integracion",
                    "categoria",
                    "icono",
                    "icon_source",
                ],
                title="Metadatos detectados",
            )
        except Exception as exc:
            self._print_error(exc)

    def _apk_register(self, apk_path: str, *, run_mobsf: bool) -> None:
        path = Path(apk_path)
        if not path.exists():
            self.console.print(f"[red]La ruta no existe dentro del contenedor:[/red] {apk_path}")
            return
        try:
            from app.application.services.app_analysis_service import AppAnalysisService
            from app.application.services.app_registration_service import AppRegistrationService

            service = AppRegistrationService(self.db)
            prepared = service.register_local_apk(
                apk_path=apk_path,
                source_label="admin_console",
            )
            self.db.commit()
            messages = list(prepared.messages)
            if run_mobsf:
                report, analysis_messages = AppAnalysisService(
                    self.db
                ).ensure_mobsf_reports([prepared])[0]
                prepared.app_version = report.version_app
                messages.extend(analysis_messages)
                self.db.commit()
            else:
                messages.append("[MOBSF] MobSF no se lanza porque --run-mobsf no fue indicado.")

            self.console.print(
                Panel("APK registrado correctamente.", title="Resultado", border_style="green")
            )
            self._print_messages(messages)
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
                ["id_app", "nombre", "version", "modelo_integracion", "ruta_apk", "estado_mobsf"],
                title="APK registrado",
            )
        except Exception as exc:
            self.db.rollback()
            self._print_error(exc)

    def _mobsf_health(self) -> None:
        try:
            from app.infrastructure.external.mobsf_client import check_mobsf_health

            result = check_mobsf_health()
            style = "green" if result.get("available") else "red"
            status = "OK" if result.get("available") else "ERROR"
            self.console.print(
                Panel(
                    f"MobSF: [{style}]{status}[/{style}]\nURL: {result.get('mobsf_url')}\n"
                    f"HTTP: {result.get('status_code') or ''}\nFinal URL: {result.get('final_url') or ''}\n"
                    f"Error: {result.get('error') or ''}",
                    title="MobSF health",
                    border_style=style,
                )
            )
        except Exception as exc:
            self._print_error(exc)

    def _mobsf_analyze(self, *, id_app: str, version: str) -> None:
        try:
            from app.application.services.app_analysis_service import AppAnalysisService
            from app.application.services.app_registration_service import PreparedAppVersion
            from app.infrastructure.persistence.repositories.application_repository import ApplicationRepository
            from app.infrastructure.persistence.repositories.app_version_repository import AppVersionRepository
            from app.schemas.comparisons import SelectedAppMetadata

            app = ApplicationRepository(self.db).find_by_id(id_app)
            app_version = AppVersionRepository(self.db).find_by_id(id_app, version)
            if app is None or app_version is None:
                self.console.print(
                    f"[red]No existe version_app para id_app={id_app!r}, version={version!r}[/red]"
                )
                return
            if not app_version.ruta_apk:
                self.console.print("[red]La versión no tiene ruta_apk registrada.[/red]")
                return
            if not Path(app_version.ruta_apk).exists():
                self.console.print(
                    f"[red]El archivo ruta_apk no existe:[/red] {app_version.ruta_apk}"
                )
                return
            selected_app = SelectedAppMetadata(
                app_id=app.id_app,
                title=app.nombre,
                developer=app.desarrollador,
                icon=app.icono,
                genre=app.categoria or app_version.categoria,
                version=app_version.version,
                version_date=(
                    app_version.fecha_version.isoformat()
                    if app_version.fecha_version
                    else None
                ),
                selected_version=app_version.version,
            )
            prepared = PreparedAppVersion(
                selected_app=selected_app,
                application=app,
                app_version=app_version,
                apk_path=Path(app_version.ruta_apk),
                app_already_registered=True,
                version_already_registered=True,
                messages=[f"[MOBSF] Análisis manual solicitado para {id_app} {version}."],
            )
            report, messages = AppAnalysisService(self.db).ensure_mobsf_reports([prepared])[0]
            self.db.commit()
            self.console.print(
                Panel("Análisis MobSF finalizado.", title="MobSF", border_style="green")
            )
            self._print_messages(messages)
            self._print_rows(
                [
                    {
                        "estado_mobsf": _value(report.version_app.estado_mobsf),
                        "hash_mobsf": report.version_app.hash_mobsf,
                        "ruta_informe_mobsf": report.version_app.ruta_informe_mobsf,
                    }
                ],
                ["estado_mobsf", "hash_mobsf", "ruta_informe_mobsf"],
                title="Resultado MobSF",
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
            ["id_mastg", "nombre", "categoria_masvs", "origen", "referencia_script_implementacion"],
            title="Pruebas MASTG",
        )

    def _mastg_test_show(self, test_id: str) -> None:
        test_row = self.db.execute(text("""
            SELECT id_mastg, nombre, descripcion, categoria_masvs, perfil, origen, referencia_script_implementacion
            FROM prueba_mastg
            WHERE id_mastg = :id_mastg
        """), {"id_mastg": test_id}).mappings().first()
        if test_row is None:
            self.console.print(f"[red]No existe la prueba MASTG:[/red] {test_id}")
            return
        indexes = self.db.execute(text("""
            SELECT i.id_indice, i.nombre
            FROM formar_parte fp
            JOIN indice_privacidad i ON i.id_indice = fp.id_indice
            WHERE fp.id_mastg = :id_mastg
            ORDER BY i.id_indice
        """), {"id_mastg": test_id}).mappings().all()
        self._print_rows(
            [test_row],
            ["id_mastg", "nombre", "descripcion", "categoria_masvs", "perfil", "origen", "referencia_script_implementacion"],
            title="Detalle de prueba MASTG",
        )
        self._print_rows(indexes, ["id_indice", "nombre"], title="Índices que incluyen la prueba")

    def _mastg_indexes(self) -> None:
        from app.application.services.mastg.mastg_evaluation_service import MastgEvaluationService

        rows = MastgEvaluationService(self.db).list_indexes()
        self._print_rows(
            rows,
            ["id_indice", "nombre", "descripcion", "total_pruebas"],
            title="Índices de privacidad",
        )

    def _mastg_index_show(self, index_id: str) -> None:
        index = self.db.execute(text("""
            SELECT i.id_indice, i.nombre, i.descripcion, i.ruta_del_script, COUNT(fp.id_mastg) AS total_pruebas
            FROM indice_privacidad i
            LEFT JOIN formar_parte fp ON fp.id_indice = i.id_indice
            WHERE i.id_indice = :index_id
            GROUP BY i.id_indice, i.nombre, i.descripcion, i.ruta_del_script
        """), {"index_id": index_id}).mappings().first()
        if index is None:
            self.console.print(f"[red]No existe el índice:[/red] {index_id}")
            return
        self._print_rows(
            [index],
            ["id_indice", "nombre", "descripcion", "ruta_del_script", "total_pruebas"],
            title="Índice",
        )
        rows = self._tests_for_index(index_id)
        self._print_rows(
            rows,
            ["id_mastg", "nombre", "categoria_masvs", "origen", "referencia_script_implementacion"],
            title="Pruebas del índice",
        )

    def _mastg_index_create(self) -> None:
        try:
            index_id = Prompt.ask("id_indice").strip()
            name = Prompt.ask("nombre").strip()
            description = Prompt.ask("descripción", default="").strip()
            if not index_id or not name:
                self.console.print("[red]id_indice y nombre son obligatorios.[/red]")
                return
            if self._index_exists(index_id):
                self.console.print(f"[red]Ya existe un índice con id_indice={index_id!r}.[/red]")
                return
            tests = self._all_mastg_tests()
            if not tests:
                self.console.print("[yellow]No hay pruebas MASTG disponibles.[/yellow]")
                return
            numbered = {str(pos): row["id_mastg"] for pos, row in enumerate(tests, start=1)}
            self._print_rows(
                [
                    {
                        "numero": pos,
                        "id_mastg": row["id_mastg"],
                        "nombre": row["nombre"],
                        "categoria_masvs": row.get("categoria_masvs"),
                        "origen": row.get("origen"),
                    }
                    for pos, row in enumerate(tests, start=1)
                ],
                ["numero", "id_mastg", "nombre", "categoria_masvs", "origen"],
                title="Pruebas disponibles",
            )
            selected_raw = Prompt.ask("IDs o números separados por coma").strip()
            selected_ids = self._parse_selected_tests(
                selected_raw,
                numbered,
                {row["id_mastg"] for row in tests},
            )
            if not selected_ids:
                self.console.print("[red]Debes seleccionar al menos una prueba válida.[/red]")
                return
            tests_by_id = {row["id_mastg"]: row for row in tests}
            self._print_rows(
                [
                    {
                        "id_indice": index_id,
                        "nombre": name,
                        "descripcion": description,
                        "total_pruebas": len(selected_ids),
                    }
                ],
                ["id_indice", "nombre", "descripcion", "total_pruebas"],
                title="Resumen del índice a crear",
            )
            self._print_rows(
                [tests_by_id[test_id] for test_id in selected_ids],
                ["id_mastg", "nombre", "categoria_masvs", "origen"],
                title="Pruebas seleccionadas",
            )
            if not Confirm.ask("¿Crear índice?", default=False):
                self.console.print("[yellow]Operación cancelada.[/yellow]")
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
            self.console.print(
                f"[green]Índice creado correctamente: {index_id} ({len(selected_ids)} pruebas).[/green]"
            )
        except Exception as exc:
            self.db.rollback()
            self._print_error(exc)

    def _mastg_index_delete(self, index_id: str) -> None:
        try:
            index = self.db.execute(text("""
                SELECT i.id_indice, i.nombre, i.descripcion, COUNT(fp.id_mastg) AS total_pruebas
                FROM indice_privacidad i
                LEFT JOIN formar_parte fp ON fp.id_indice = i.id_indice
                WHERE i.id_indice = :index_id
                GROUP BY i.id_indice, i.nombre, i.descripcion
            """), {"index_id": index_id}).mappings().first()
            if index is None:
                self.console.print(f"[red]No existe el índice:[/red] {index_id}")
                return
            self._print_rows(
                [index],
                ["id_indice", "nombre", "descripcion", "total_pruebas"],
                title="Índice a eliminar",
            )
            self.console.print(
                "[yellow]No se borrarán pruebas MASTG ni resultados evaluar; solo el índice y sus relaciones.[/yellow]"
            )
            typed = Prompt.ask(
                f"Para confirmar, escribe el ID exacto ({index_id})",
                default="",
            ).strip()
            if typed != index_id:
                self.console.print("[yellow]Confirmación no válida. Operación cancelada.[/yellow]")
                return
            if not Confirm.ask("¿Eliminar índice definitivamente?", default=False):
                self.console.print("[yellow]Operación cancelada.[/yellow]")
                return
            self.db.execute(text("DELETE FROM formar_parte WHERE id_indice = :index_id"), {"index_id": index_id})
            self.db.execute(text("DELETE FROM indice_privacidad WHERE id_indice = :index_id"), {"index_id": index_id})
            self.db.commit()
            self.console.print(f"[green]Índice eliminado correctamente: {index_id}[/green]")
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
            self.console.print(
                Panel("Evaluación MASTG finalizada.", title="MASTG", border_style="green")
            )
            self._print_score(result.get("score") or {})
            self._print_status_summary(result.get("results", []))
            self._print_rows(
                result.get("results", []),
                ["id_mastg", "resultado", "summary"],
                title="Resultados por prueba",
            )
        except Exception as exc:
            self.db.rollback()
            self._print_error(exc)

    def _mastg_reevaluate_all(self) -> None:
        try:
            from app.application.services.mastg.mastg_evaluation_service import MastgEvaluationService

            versions = self.db.execute(text("""
                SELECT id_app, version FROM version_app ORDER BY id_app, version
            """)).mappings().all()
            indexes = self.db.execute(text("""
                SELECT id_indice FROM indice_privacidad ORDER BY id_indice
            """)).mappings().all()
            total = len(versions) * len(indexes)
            self.console.print(
                Panel(
                    f"Se van a reevaluar {len(versions)} versiones con {len(indexes)} índices.\n"
                    f"Total ejecuciones: {total}",
                    title="Reevaluación masiva",
                    border_style="yellow",
                )
            )
            if total == 0:
                self.console.print("[yellow]No hay ejecuciones pendientes.[/yellow]")
                return
            if not Confirm.ask("¿Continuar con la reevaluación masiva?", default=False):
                self.console.print("[yellow]Operación cancelada.[/yellow]")
                return
            service = MastgEvaluationService(self.db)
            ok = 0
            errors: list[dict[str, str]] = []
            for version_row in versions:
                for index_row in indexes:
                    label = (
                        f"{version_row['id_app']} {version_row['version']} "
                        f"con {index_row['id_indice']}"
                    )
                    self.console.print(f"[cyan]Evaluando[/cyan] {label}")
                    try:
                        service.evaluate_version(
                            index_id=index_row["id_indice"],
                            id_app=version_row["id_app"],
                            version=version_row["version"],
                        )
                        ok += 1
                    except Exception as exc:  # continuar con el resto
                        self.db.rollback()
                        errors.append({"ejecucion": label, "error": str(exc)})
                        self.console.print(f"[red]Error en {label}:[/red] {exc}")
            self.console.print(
                Panel(
                    f"Total ejecuciones: {total}\nCorrectas: {ok}\nErrores: {len(errors)}",
                    title="Resumen final",
                    border_style="green" if not errors else "yellow",
                )
            )
            if errors:
                self._print_rows(errors, ["ejecucion", "error"], title="Errores")
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
            SELECT id_mastg, nombre, categoria_masvs, origen
            FROM prueba_mastg
            ORDER BY id_mastg
        """)).mappings().all()]

    def _index_exists(self, index_id: str) -> bool:
        return self.db.execute(
            text("SELECT 1 FROM indice_privacidad WHERE id_indice = :id"),
            {"id": index_id},
        ).first() is not None

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

    def _load_banner_counters(self) -> dict[str, Any]:
        counters: dict[str, Any] = {
            "connected": True,
            "apps": "?",
            "tests": "?",
            "indexes": "?",
            "warnings": [],
        }
        for key, table in [
            ("apps", "aplicacion"),
            ("tests", "prueba_mastg"),
            ("indexes", "indice_privacidad"),
        ]:
            try:
                counters[key] = self.db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            except Exception as exc:
                self.db.rollback()
                counters["connected"] = False
                counters["warnings"].append(f"No se pudo consultar {table}: {exc}")
        return counters

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
            self.console.print(f"[red]Error parseando argumentos:[/red] {exc}")
            return []

    def _print_error(self, exc: Exception) -> None:
        self.console.print(f"[bold red]Error:[/bold red] {exc}")
        if self.debug:
            self.console.print_exception(show_locals=False)
        else:
            self.console.print(
                "[dim]Activa PI_CHECK_ADMIN_DEBUG=true para ver la traza completa.[/dim]"
            )

    def _print_messages(self, messages: list[str]) -> None:
        if not messages:
            return
        for message in messages:
            style = "white"
            if message.startswith("[MOBSF]"):
                style = "magenta"
            elif message.startswith("[APK]"):
                style = "cyan"
            elif message.startswith("[METADATA]"):
                style = "blue"
            elif "no se lanza" in message.lower():
                style = "yellow"
            self.console.print(f"[{style}]{message}[/{style}]")

    def _print_score(self, score: dict[str, Any]) -> None:
        self._print_rows(
            [
                {
                    "score": score.get("score"),
                    "score_percent": score.get("score_percent"),
                    "coverage": score.get("coverage"),
                    "coverage_percent": score.get("coverage_percent"),
                    "total_tests": score.get("total_tests"),
                    "scorable_tests": score.get("scorable_tests"),
                }
            ],
            ["score", "score_percent", "coverage", "coverage_percent", "total_tests", "scorable_tests"],
            title="Score",
        )

    def _print_status_summary(self, results: list[dict[str, Any]]) -> None:
        counts: dict[str, int] = {}
        for item in results:
            status = str(item.get("resultado") or "")
            counts[status] = counts.get(status, 0) + 1
        self._print_rows(
            [{"resultado": key, "total": value} for key, value in sorted(counts.items())],
            ["resultado", "total"],
            title="Resumen por estados",
        )

    def _print_rows(
        self,
        rows: Iterable[Any],
        columns: list[str],
        *,
        title: str | None = None,
        max_width: int = 80,
    ) -> None:
        materialized = [dict(row) for row in rows]
        if not materialized:
            self.console.print("[yellow]Sin resultados.[/yellow]")
            return
        table = Table(
            title=title,
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=False,
        )
        for column in columns:
            table.add_column(column, overflow="fold")
        for row in materialized:
            table.add_row(
                *[
                    self._format_cell(column, row.get(column), max_width=max_width)
                    for column in columns
                ]
            )
        self.console.print(table)

    def _format_cell(self, column: str, value: Any, *, max_width: int) -> str:
        if value is None:
            return ""
        text_value = str(_value(value))
        limit = max_width if column in LONG_COLUMNS else min(max_width, 40)
        if len(text_value) > limit:
            text_value = text_value[: max(0, limit - 3)] + "..."
        if column == "resultado":
            style = STATUS_STYLES.get(text_value, "white")
            return f"[{style}]{text_value}[/{style}]"
        return text_value


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
