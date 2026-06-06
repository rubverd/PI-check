#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.application.services.privacy_index_service import PrivacyIndexService
from app.domain.entities.mastg_test import MastgTest
from app.domain.entities.privacy_index import PrivacyIndex
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.persistence.repositories.mastg_test_repository import MastgTestRepository
from app.infrastructure.persistence.repositories.privacy_index_repository import PrivacyIndexRepository


def prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default or ""


def print_test(test: MastgTest) -> None:
    print(f"- {test.id_mastg} | {test.nombre} | {test.owasp_category or test.categoria_masvs or '-'}")
    if test.descripcion:
        print(f"  {test.descripcion}")


def print_index(index: PrivacyIndex) -> None:
    tests = ", ".join(index.pruebas_mastg or []) or "sin pruebas"
    print(f"- {index.id_indice} | {index.nombre} | pruebas: {tests}")
    if index.descripcion:
        print(f"  {index.descripcion}")


def create_or_update_test(repo: MastgTestRepository, existing: MastgTest | None = None) -> None:
    id_mastg = prompt("ID prueba MASTG", existing.id_mastg if existing else None)
    nombre = prompt("Nombre", existing.nombre if existing else None)
    referencia = prompt("Referencia MASTG", existing.referencia_mastg if existing else id_mastg)
    descripcion = prompt("Descripción", existing.descripcion if existing else None)
    categoria = prompt("Categoría OWASP/MASVS", existing.owasp_category if existing else None)
    script = prompt("Referencia implementación", existing.referencia_script_implementacion if existing else None)
    perfil = prompt("Perfil", existing.perfil if existing else "STATIC")

    repo.save(
        MastgTest(
            id_mastg=id_mastg,
            nombre=nombre,
            referencia_script_implementacion=script or None,
            categoria_masvs=categoria or None,
            perfil=perfil or None,
            referencia_mastg=referencia or id_mastg,
            descripcion=descripcion or None,
            owasp_category=categoria or None,
        )
    )
    print(f"[CATALOG] Prueba guardada: {id_mastg}")


def create_or_update_index(repo: PrivacyIndexRepository, existing: PrivacyIndex | None = None) -> None:
    id_indice = prompt("ID índice", existing.id_indice if existing else None)
    nombre = prompt("Nombre", existing.nombre if existing else None)
    descripcion = prompt("Descripción", existing.descripcion if existing else None)
    script = prompt("Ruta script", existing.ruta_del_script if existing else None)

    repo.save(
        PrivacyIndex(
            id_indice=id_indice,
            nombre=nombre,
            descripcion=descripcion or None,
            ruta_del_script=script or None,
            pruebas_mastg=existing.pruebas_mastg if existing else [],
        )
    )
    print(f"[CATALOG] Índice guardado: {id_indice}")


def main() -> None:
    db = SessionLocal()
    test_repo = MastgTestRepository(db)
    index_repo = PrivacyIndexRepository(db)
    index_service = PrivacyIndexService(db)

    actions = {
        "1": "Listar pruebas MASTG",
        "2": "Crear prueba MASTG",
        "3": "Modificar prueba MASTG",
        "4": "Eliminar prueba MASTG",
        "5": "Listar índices de privacidad",
        "6": "Crear índice de privacidad",
        "7": "Modificar índice de privacidad",
        "8": "Eliminar índice de privacidad",
        "9": "Asociar prueba MASTG a índice",
        "10": "Desasociar prueba MASTG de índice",
        "11": "Ver pruebas asociadas a un índice",
        "12": "Cargar catálogo inicial recomendado",
        "13": "Salir",
    }

    try:
        while True:
            print("\n=== Gestión catálogo MASTG-lite ===")
            for key, label in actions.items():
                print(f"{key}. {label}")
            choice = input("Opción: ").strip()

            if choice == "1":
                for test in test_repo.list_all():
                    print_test(test)
            elif choice == "2":
                create_or_update_test(test_repo)
                db.commit()
            elif choice == "3":
                id_mastg = prompt("ID prueba a modificar")
                existing = test_repo.find_by_id(id_mastg)
                if not existing:
                    print("[CATALOG] No existe la prueba.")
                    continue
                create_or_update_test(test_repo, existing)
                db.commit()
            elif choice == "4":
                id_mastg = prompt("ID prueba a eliminar")
                deleted = test_repo.delete(id_mastg)
                db.commit()
                print("[CATALOG] Prueba eliminada." if deleted else "[CATALOG] No existe la prueba.")
            elif choice == "5":
                for index in index_repo.list_all():
                    print_index(index)
            elif choice == "6":
                create_or_update_index(index_repo)
                db.commit()
            elif choice == "7":
                id_indice = prompt("ID índice a modificar")
                existing = index_repo.find_by_id(id_indice)
                if not existing:
                    print("[CATALOG] No existe el índice.")
                    continue
                create_or_update_index(index_repo, existing)
                db.commit()
            elif choice == "8":
                id_indice = prompt("ID índice a eliminar")
                deleted = index_repo.delete(id_indice)
                db.commit()
                print("[CATALOG] Índice eliminado." if deleted else "[CATALOG] No existe el índice.")
            elif choice == "9":
                id_indice = prompt("ID índice")
                id_mastg = prompt("ID prueba MASTG")
                index_repo.add_test(id_indice, id_mastg)
                db.commit()
                print(f"[CATALOG] Asociada {id_mastg} a {id_indice}.")
            elif choice == "10":
                id_indice = prompt("ID índice")
                id_mastg = prompt("ID prueba MASTG")
                removed = index_repo.remove_test(id_indice, id_mastg)
                db.commit()
                print("[CATALOG] Asociación eliminada." if removed else "[CATALOG] No existía la asociación.")
            elif choice == "11":
                id_indice = prompt("ID índice")
                test_ids = index_repo.list_test_ids(id_indice)
                print(f"[CATALOG] Pruebas en {id_indice}: {', '.join(test_ids) or 'ninguna'}")
            elif choice == "12":
                created_tests, created_indices, created_links = index_service.load_recommended_catalog()
                db.commit()
                print(
                    "[CATALOG] Catálogo recomendado cargado. "
                    f"Pruebas nuevas: {created_tests}, índices nuevos: {created_indices}, asociaciones nuevas: {created_links}."
                )
            elif choice == "13":
                print("Saliendo.")
                break
            else:
                print("Opción no válida.")
    except KeyboardInterrupt:
        print("\nSaliendo.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
