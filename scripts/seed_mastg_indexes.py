from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_session_local():
    try:
        from app.infrastructure.database.session import SessionLocal  # type: ignore

        return SessionLocal
    except Exception:
        database_url = (
            os.getenv("DATABASE_URL")
            or os.getenv("SQLALCHEMY_DATABASE_URL")
            or os.getenv("POSTGRES_URL")
        )

        if not database_url:
            raise RuntimeError(
                "No se pudo importar SessionLocal ni encontrar DATABASE_URL/SQLALCHEMY_DATABASE_URL/POSTGRES_URL."
            )

        engine = create_engine(database_url)
        return sessionmaker(bind=engine, autoflush=False, autocommit=False)


TESTS = [
    {
        "id_mastg": "MASTG-TEST-0254",
        "nombre": "Permisos peligrosos",
        "descripcion": "Evalúa la presencia de permisos Android peligrosos declarados por la aplicación.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.mobsf_json.prueba_mastg_0254",
        "categoria_masvs": "MASVS-PLATFORM",
        "perfil": "mHealth",
        "origen": "MOBSF_JSON",
        "tipo_relacion": "DIRECT",
    },
    {
        "id_mastg": "MASTG-TEST-0262",
        "nombre": "Backup",
        "descripcion": "Evalúa configuración de backup a partir de evidencias MobSF y reglas PI-check.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.mixed.prueba_mastg_0262",
        "categoria_masvs": "MASVS-STORAGE",
        "perfil": "mHealth",
        "origen": "MIXED",
        "tipo_relacion": "PARTIAL",
    },
    {
        "id_mastg": "MASTG-TEST-0235",
        "nombre": "Cleartext Traffic",
        "descripcion": "Evalúa si la aplicación permite tráfico cleartext según evidencias del informe MobSF.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.mobsf_json.prueba_mastg_0235",
        "categoria_masvs": "MASVS-NETWORK",
        "perfil": "mHealth",
        "origen": "MOBSF_JSON",
        "tipo_relacion": "DIRECT",
    },
    {
        "id_mastg": "MASTG-TEST-0233",
        "nombre": "URLs HTTP",
        "descripcion": "Detecta URLs HTTP públicas aplicando filtrado propio PI-check sobre evidencias MobSF.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.mixed.prueba_mastg_0233",
        "categoria_masvs": "MASVS-NETWORK",
        "perfil": "mHealth",
        "origen": "MIXED",
        "tipo_relacion": "PARTIAL",
    },
    {
        "id_mastg": "MASTG-TEST-0231",
        "nombre": "Logging",
        "descripcion": "Evalúa evidencias relacionadas con logging potencialmente sensible.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.mobsf_json.prueba_mastg_0231",
        "categoria_masvs": "MASVS-PRIVACY",
        "perfil": "mHealth",
        "origen": "MOBSF_JSON",
        "tipo_relacion": "DIRECT",
    },
    {
        "id_mastg": "MASTG-TEST-0202",
        "nombre": "Almacenamiento externo",
        "descripcion": "Evalúa evidencias de almacenamiento externo o exposición local de datos.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.mobsf_json.prueba_mastg_0202",
        "categoria_masvs": "MASVS-STORAGE",
        "perfil": "mHealth",
        "origen": "MOBSF_JSON",
        "tipo_relacion": "DIRECT",
    },
    {
        "id_mastg": "MASTG-TEST-0206",
        "nombre": "Exposición de PII en red",
        "descripcion": "Evalúa evidencias MobSF relacionadas con exposición de PII en comunicaciones de red.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.mobsf_json.prueba_mastg_0206",
        "categoria_masvs": "MASVS-PRIVACY",
        "perfil": "mHealth",
        "origen": "MOBSF_JSON",
        "tipo_relacion": "DIRECT",
    },
    {
        "id_mastg": "MASTG-TEST-0255",
        "nombre": "Minimización de privilegios",
        "descripcion": "Evalúa minimización de permisos combinando evidencias MobSF y reglas PI-check.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.mixed.prueba_mastg_0255",
        "categoria_masvs": "MASVS-PRIVACY",
        "perfil": "mHealth",
        "origen": "MIXED",
        "tipo_relacion": "INFERRED",
    },
    {
        "id_mastg": "MASTG-TEST-0318",
        "nombre": "SDK APIs sensibles",
        "descripcion": "Detecta referencias a APIs sensibles mediante análisis estático propio sobre el APK.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.picheck_static.prueba_mastg_0318",
        "categoria_masvs": "MASVS-PRIVACY",
        "perfil": "mHealth",
        "origen": "PICHECK_STATIC",
        "tipo_relacion": "CUSTOM_STATIC",
    },
    {
        "id_mastg": "MASTG-TEST-0217",
        "nombre": "TLS inseguro explícito",
        "descripcion": "Detecta patrones estáticos compatibles con validación TLS insegura.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.picheck_static.prueba_mastg_0217",
        "categoria_masvs": "MASVS-NETWORK",
        "perfil": "mHealth",
        "origen": "PICHECK_STATIC",
        "tipo_relacion": "CUSTOM_STATIC",
    },
    {
        "id_mastg": "MASTG-TEST-0286",
        "nombre": "CAs de usuario",
        "descripcion": "Evalúa configuración relacionada con confianza en CAs de usuario.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.picheck_static.prueba_mastg_0286",
        "categoria_masvs": "MASVS-NETWORK",
        "perfil": "mHealth",
        "origen": "PICHECK_STATIC",
        "tipo_relacion": "CUSTOM_STATIC",
    },
    {
        "id_mastg": "PI-CHECK-HTTP-CONTEXT",
        "nombre": "Contexto HTTP PI-check",
        "descripcion": "Prueba propia PI-check para analizar el contexto de uso de URLs HTTP.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.picheck_static.prueba_picheck_http_context",
        "categoria_masvs": "PI-CHECK-PRIVACY",
        "perfil": "mHealth",
        "origen": "PICHECK_STATIC",
        "tipo_relacion": "CUSTOM_STATIC",
    },
    {
        "id_mastg": "PI-CHECK-BACKUP-RULES",
        "nombre": "Reglas backup PI-check",
        "descripcion": "Prueba propia PI-check para analizar reglas de backup y exclusiones de datos.",
        "referencia_script_implementacion": "app.application.services.mastg.evaluators.picheck_static.prueba_picheck_backup_rules",
        "categoria_masvs": "PI-CHECK-STORAGE",
        "perfil": "mHealth",
        "origen": "PICHECK_STATIC",
        "tipo_relacion": "CUSTOM_STATIC",
    },
]


INDEXES = [
    {
        "id_indice": "picheck_mhealth_v1",
        "nombre": "Índice PI-check mHealth v1",
        "descripcion": (
            "Índice general para aplicaciones mHealth que combina evidencias procedentes "
            "de MobSF con evaluadores estáticos propios de PI-check."
        ),
        "ruta_del_script": None,
        "tests": [
            "MASTG-TEST-0254",
            "MASTG-TEST-0262",
            "MASTG-TEST-0235",
            "MASTG-TEST-0233",
            "MASTG-TEST-0231",
            "MASTG-TEST-0202",
            "MASTG-TEST-0206",
            "MASTG-TEST-0255",
            "MASTG-TEST-0318",
            "MASTG-TEST-0217",
            "MASTG-TEST-0286",
        ],
    },
    {
        "id_indice": "picheck_static_custom_v1",
        "nombre": "Índice PI-check Static Custom v1",
        "descripcion": (
            "Índice formado únicamente por pruebas estáticas implementadas en el backend de PI-check."
        ),
        "ruta_del_script": None,
        "tests": [
            "MASTG-TEST-0318",
            "MASTG-TEST-0217",
            "MASTG-TEST-0286",
            "PI-CHECK-HTTP-CONTEXT",
            "PI-CHECK-BACKUP-RULES",
        ],
    },
]


def main() -> None:
    SessionLocal = build_session_local()
    session = SessionLocal()

    try:
        for test in TESTS:
            session.execute(
                text(
                    """
                    INSERT INTO prueba_mastg (
                        id_mastg,
                        nombre,
                        descripcion,
                        referencia_script_implementacion,
                        categoria_masvs,
                        perfil,
                        origen,
                        tipo_relacion
                    )
                    VALUES (
                        :id_mastg,
                        :nombre,
                        :descripcion,
                        :referencia_script_implementacion,
                        :categoria_masvs,
                        :perfil,
                        :origen,
                        :tipo_relacion
                    )
                    ON CONFLICT (id_mastg)
                    DO UPDATE SET
                        nombre = EXCLUDED.nombre,
                        descripcion = EXCLUDED.descripcion,
                        referencia_script_implementacion = EXCLUDED.referencia_script_implementacion,
                        categoria_masvs = EXCLUDED.categoria_masvs,
                        perfil = EXCLUDED.perfil,
                        origen = EXCLUDED.origen,
                        tipo_relacion = EXCLUDED.tipo_relacion
                    """
                ),
                test,
            )

        for index in INDEXES:
            session.execute(
                text(
                    """
                    INSERT INTO indice_privacidad (
                        id_indice,
                        nombre,
                        descripcion,
                        ruta_del_script
                    )
                    VALUES (
                        :id_indice,
                        :nombre,
                        :descripcion,
                        :ruta_del_script
                    )
                    ON CONFLICT (id_indice)
                    DO UPDATE SET
                        nombre = EXCLUDED.nombre,
                        descripcion = EXCLUDED.descripcion,
                        ruta_del_script = EXCLUDED.ruta_del_script
                    """
                ),
                {
                    "id_indice": index["id_indice"],
                    "nombre": index["nombre"],
                    "descripcion": index["descripcion"],
                    "ruta_del_script": index["ruta_del_script"],
                },
            )

            for id_mastg in index["tests"]:
                session.execute(
                    text(
                        """
                        INSERT INTO formar_parte (
                            id_indice,
                            id_mastg
                        )
                        VALUES (
                            :id_indice,
                            :id_mastg
                        )
                        ON CONFLICT (id_indice, id_mastg)
                        DO NOTHING
                        """
                    ),
                    {
                        "id_indice": index["id_indice"],
                        "id_mastg": id_mastg,
                    },
                )

        session.commit()

        print("Seed MASTG/PI-check aplicado correctamente.")
        print(f"Pruebas insertadas/actualizadas: {len(TESTS)}")
        print(f"Índices insertados/actualizados: {len(INDEXES)}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
