# Despliegue PI-check en VM UVA

Esta guía describe cómo desplegar PI-check desde cero en la VM UVA actual. No contiene credenciales reales y no requiere acceder a la VM desde Codex.

## Perfil de la VM actual

* SSH: `virtual.lab.inf.uva.es:20491`.
* URL pública esperada de API/HTTPS: `https://virtual.lab.inf.uva.es:20492`.
* IP interna de la VM: `10.0.20.49`.
* IP pública del host externo: `157.88.125.240`.
* Forwarding confirmado para esta VM: `virtual.lab.inf.uva.es:20492 -> VM:8443`.
* Por tanto, en `.env` debe quedar:

```env
PICHECK_HTTPS_PORT=8443
```

nginx sigue escuchando en `443 ssl` dentro del contenedor. Docker Compose publica nginx mediante `${PICHECK_HTTPS_PORT}:443`, es decir, `8443:443` para esta VM concreta. El backend FastAPI (`8088`) no debe exponerse públicamente; Compose lo publica en `127.0.0.1:${PICHECK_API_PORT}:8088` solo para pruebas locales en la VM.

> Nota: `localhost:20492` dentro de la VM no tiene por qué funcionar. El puerto `20492` es el puerto público externo; dentro de la VM se prueba contra `localhost:8443`.

## Borrar un despliegue anterior

Si quieres empezar completamente de cero en la VM:

```bash
cd ~/PI-check
docker compose down -v --remove-orphans
cd ..
rm -rf PI-check
```

`docker compose down -v` borra los volúmenes, incluida la base de datos PostgreSQL. Úsalo solo si quieres perder el estado anterior.

## Clonar de nuevo

```bash
git clone <URL_DEL_REPOSITORIO> PI-check
cd PI-check
```

## Ejecutar bootstrap específico UVA

Para la VM UVA actual:

```bash
./scripts/bootstrap_vm_uva.sh --force-env
```

Este wrapper llama a `scripts/bootstrap_deploy.sh` con estos valores por defecto:

```bash
PUBLIC_DNS="virtual.lab.inf.uva.es"
PUBLIC_IP="157.88.125.240"
VM_IP="10.0.20.49"
PICHECK_HTTPS_PORT="8443"
POSTGRES_PASSWORD="picheck"
MOBSF_API_KEY="picheck"
```

Puedes sobreescribir cualquiera de ellos antes de ejecutar el script si la infraestructura cambia:

```bash
POSTGRES_PASSWORD="otra-password" MOBSF_API_KEY="otra-api-key" ./scripts/bootstrap_vm_uva.sh --force-env
```

Para otra máquina distinta, no uses este wrapper salvo que cambies valores; usa directamente `scripts/bootstrap_deploy.sh` con `PUBLIC_DNS`, `PUBLIC_IP`, `VM_IP` y `PICHECK_HTTPS_PORT` adecuados.

## Qué crea el bootstrap

El bootstrap prepara:

* `.env` desde `.env.example` si no existe, o lo actualiza con `--force-env`;
* `backend/artifacts/manual_uploads`;
* `backend/artifacts/tmp/apks`;
* `backend/artifacts/reports/mobsf`;
* `backend/artifacts/reports/mastg`;
* `backend/artifacts/reports/comparisons`;
* `nginx/certs`;
* `mobile/app/src/main/res/raw`;
* CA persistente en `~/.picheck/certs`;
* copia pública de la CA en `nginx/certs/picheck_ca.crt`;
* copia pública de la CA para Android en `mobile/app/src/main/res/raw/picheck_ca.crt`;
* certificado/clave de servidor nginx en `nginx/certs/picheck-server.crt` y `nginx/certs/picheck-server.key`.

La clave privada de la CA vive fuera del repo:

```text
~/.picheck/certs/picheck_ca.key
```

No la copies al repositorio.

## Revisar `.env`

Después del bootstrap:

```bash
nano .env
```

Para esta VM debe mantenerse:

```env
PICHECK_HTTPS_PORT=8443
```

El script usa por defecto `POSTGRES_PASSWORD=picheck` y `MOBSF_API_KEY=picheck` si no especificas otros valores. Cámbialos si quieres credenciales diferentes en tu despliegue real.

## Levantar servicios

```bash
docker compose config
docker compose build
docker compose up -d
docker compose exec backend alembic upgrade head
```

## Probar localmente desde la VM

```bash
curl -k https://localhost:8443/api/apps/registered
```

También puedes comprobar contenedores:

```bash
docker compose ps
```

## Probar desde fuera

Desde tu portátil u otra red con acceso al puerto público:

```bash
curl -k https://virtual.lab.inf.uva.es:20492/api/apps/registered
```

O en navegador:

```text
https://virtual.lab.inf.uva.es:20492/api/apps/registered
```

## Certificado Android

Android confía en nginx mediante:

```text
mobile/app/src/main/res/raw/picheck_ca.crt
```

Ese archivo debe coincidir con la CA que firma `nginx/certs/picheck-server.crt`.

* Si regeneras la CA, recompila e instala de nuevo la app Android.
* Si solo regeneras el certificado de servidor usando la misma CA persistente, no hace falta cambiar la app.
* Si cambias dominio o puerto público, revisa el `BASE_URL` centralizado en `PiCheckApiClient.kt` y recompila la app.

## Registrar APK local

Copia APK/XAPK/APKS/APKM al host en `backend/artifacts/manual_uploads` y llama al endpoint con la ruta del contenedor:

```bash
curl -k -X POST "https://localhost:8443/api/apps/register-local-apk" \
  -H "Content-Type: application/json" \
  -d '{
    "apk_path": "/app/artifacts/manual_uploads/example-legacy.apk",
    "title": "Example Health",
    "developer": "Unknown",
    "category": "Health & Fitness",
    "run_mobsf": false,
    "source_label": "manual_dataset"
  }'
```

## Archivos que no se deben commitear

No subas:

* `.env`;
* `~/.picheck/certs/picheck_ca.key`;
* `nginx/certs/picheck-server.key`;
* `nginx/certs/*.csr`;
* `nginx/certs/*.srl`;
* APKs del dataset en `backend/artifacts/manual_uploads`;
* reports y temporales de `backend/artifacts`.

`.gitignore` cubre estos casos, pero revisa siempre `git status` antes de hacer commit.
