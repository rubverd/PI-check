# PI-check

PI-check compara privacidad y seguridad de aplicaciones Android, con foco en apps mHealth y en la distinción entre integraciones `HEALTH_CONNECT`, `LEGACY` y `UNKNOWN`.

El proyecto incluye:

* backend FastAPI con PostgreSQL, SQLAlchemy y Alembic;
* MobSF para análisis estático;
* nginx como proxy inverso HTTPS;
* Docker Compose para despliegue;
* app Android Kotlin/Jetpack Compose.

## Despliegue rápido con Docker Compose

Para una máquina nueva o una VM recién creada, usa primero el bootstrap de despliegue:

```bash
git clone <URL_DEL_REPOSITORIO> PI-check
cd PI-check
./scripts/bootstrap_deploy.sh --force-env
```

Después revisa `.env` y levanta los servicios:

```bash
docker compose config
docker compose build
docker compose up -d
docker compose exec backend alembic upgrade head
```

Prueba la API HTTPS local del host:

```bash
curl -k https://localhost:${PICHECK_HTTPS_PORT}/api/apps/registered
```

## Bootstrap para la VM UVA

La VM UVA actual usa este perfil:

* dominio público: `virtual.lab.inf.uva.es`;
* puerto público HTTPS/API: `20492`;
* forwarding externo: `virtual.lab.inf.uva.es:20492 -> VM:8443`;
* IP interna VM: `10.0.20.49`;
* IP pública externa: `157.88.125.240`.

En esa VM ejecuta:

```bash
./scripts/bootstrap_vm_uva.sh --force-env
```

El wrapper configura internamente:

```bash
PUBLIC_DNS="virtual.lab.inf.uva.es"
PUBLIC_IP="157.88.125.240"
VM_IP="10.0.20.49"
PICHECK_HTTPS_PORT="8443"
```

Android debe apuntar a:

```text
https://virtual.lab.inf.uva.es:20492
```

## Bootstrap en otra máquina

Para otro host, cambia DNS/IP/puerto mediante variables:

```bash
PUBLIC_DNS="mi-servidor.example.org" \
PUBLIC_IP="203.0.113.10" \
VM_IP="192.168.1.50" \
PICHECK_HTTPS_PORT="8443" \
POSTGRES_PASSWORD="picheck" \
MOBSF_API_KEY="picheck" \
./scripts/bootstrap_deploy.sh --force-env
```

También puedes añadir SAN extra:

```bash
EXTRA_DNS="otro-dns.example.org" EXTRA_IP="192.168.1.51" ./scripts/bootstrap_deploy.sh
```

## Certificados y CA Android

El bootstrap crea o reutiliza una CA persistente en:

```text
~/.picheck/certs/picheck_ca.crt
~/.picheck/certs/picheck_ca.key
```

Diferencias importantes:

* `picheck_ca.crt`: certificado público de la CA. Puede copiarse a nginx y Android.
* `picheck_ca.key`: clave privada de la CA. **No debe commitearse nunca**.
* `nginx/certs/picheck-server.crt`: certificado de servidor usado por nginx.
* `nginx/certs/picheck-server.key`: clave privada de servidor nginx. **No debe commitearse nunca**.

La app Android confía en nginx mediante:

```text
mobile/app/src/main/res/raw/picheck_ca.crt
```

Ese archivo debe coincidir con la CA que firma el certificado del servidor nginx.

* Si regeneras la CA, recompila e instala de nuevo la app Android.
* Si solo regeneras el certificado de servidor con la misma CA, no hace falta cambiar la app.
* Si cambias dominio/puerto público, ajusta el `BASE_URL` centralizado en `PiCheckApiClient.kt` y recompila Android.

## Archivos que no deben commitearse

No subas al repositorio:

* `.env` ni variantes con secretos;
* `picheck_ca.key`;
* `picheck-server.key`;
* CSR/SRL generados por OpenSSL;
* APK/XAPK/APKS/APKM del dataset;
* artefactos de análisis y reports generados.

`.gitignore` ya cubre esos casos habituales, pero revisa siempre `git status` antes de hacer commit.

## Utilidad opcional de limpieza Android

`scripts/clean_android_stale_models.sh` se conserva como utilidad opcional para máquinas que hayan tenido merges antiguos con modelos duplicados. No hay workarounds en Gradle para ocultar ficheros Kotlin: si Android Studio muestra redeclaraciones por ficheros locales obsoletos, ejecuta:

```bash
./scripts/clean_android_stale_models.sh
```

## Ingesta de APKs y deduplicación

El backend usa una lógica centralizada de ingesta para APKs descargados con `apkeep`, APKs locales del servidor y APKs subidos por multipart. El flujo optimizado comprueba primero si la versión solicitada ya existe; si existe, evita descargar APK, reutiliza `ruta_apk` y reutiliza el informe MobSF si está disponible. Si la versión no es concreta o no existe, descarga solo los APKs necesarios y vuelve a comprobar duplicados tras extraer metadatos del archivo.

Los APKs conservados se guardan en una ruta gestionada:

```text
${APK_STORAGE_DIR}/{id_app}/{version}/
```

Por defecto:

```text
/app/artifacts/apks/{id_app}/{version}/
```

Los APKs subidos desde Android o `curl` se guardan primero en `${APK_UPLOAD_STAGING_DIR}` y después se mueven a `APK_STORAGE_DIR` si se registra una versión nueva. Si tras extraer metadatos se detecta que la versión ya existía, se elimina el temporal y se reutiliza la versión registrada.

### Registrar un APK local del servidor

Primero copia el archivo a la carpeta permitida:

```bash
cp example.apk backend/artifacts/manual_uploads/
```

Después llama al endpoint con la ruta del contenedor:

```bash
curl -k -X POST "https://localhost:8443/api/apps/register-local-apk" \
  -H "Content-Type: application/json" \
  -d '{
    "apk_path": "/app/artifacts/manual_uploads/example.apk",
    "title": "Example Health",
    "developer": "Unknown",
    "category": "Health & Fitness",
    "run_mobsf": false,
    "version_date": "2025-06-01"
  }'
```

Por seguridad, `register-local-apk` solo acepta rutas dentro de `MANUAL_APK_UPLOAD_DIR`.

### Subir un APK por multipart

```bash
curl -k -X POST "https://localhost:8443/api/apps/upload-apk" \
  -F "file=@example.apk" \
  -F "title=Example Health" \
  -F "developer=Unknown" \
  -F "category=Health & Fitness" \
  -F "source_label=mobile_upload" \
  -F "run_mobsf=false"
```

Este endpoint requiere `python-multipart` y respeta `MAX_UPLOAD_APK_SIZE_MB`. nginx está configurado con `client_max_body_size 300M`; si aumentas el límite de subida, revisa también nginx.

### Subida desde Android

La app Android incluye una opción básica `Subir APK` en la sección de aplicaciones registradas. Usa el selector de archivos del sistema, sube el archivo por multipart a `/api/apps/upload-apk` y refresca `/api/apps/registered` al finalizar. Si cambias la URL pública del backend, mantén actualizado el `BASE_URL` centralizado en `PiCheckApiClient.kt`.

### Estructura de artifacts y reparación de rutas antiguas

Las rutas de artifacts tienen roles distintos:

- `backend/artifacts/tmp/apks`: descargas temporales de `apkeep` usadas durante comparaciones o extracción de metadatos. Debe quedar limpio tras ingestas finalizadas.
- `backend/artifacts/tmp/uploads`: staging temporal de subidas multipart antes de registrar/deduplicar.
- `backend/artifacts/apks`: almacenamiento gestionado y persistente de APK/XAPK/APKS/APKM conservados. `version_app.ruta_apk` debe apuntar aquí.
- `backend/artifacts/manual_uploads`: bandeja de entrada para APKs copiados manualmente al servidor; el registro conserva el original y copia la versión persistente a `artifacts/apks`.
- `backend/artifacts/reports/mobsf`: informes MobSF persistentes; no se deben borrar al limpiar temporales.

Para inspeccionar rutas guardadas en BD:

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT id_app, version, estado_mobsf, ruta_apk, ruta_informe_mobsf
FROM version_app
ORDER BY id_app, version;
"
```

Si existen filas antiguas con `ruta_apk` nula, inexistente o apuntando a `tmp`, usa el script de reparación:

```bash
docker compose exec backend python scripts/repair_apk_storage_paths.py
```

El script mueve a `APK_STORAGE_DIR` los APKs que todavía existan en `tmp`, actualiza `ruta_apk` y avisa con `[REPAIR]` si no puede reparar una fila porque el archivo ya no existe.

### Organización Android

La pantalla principal está separada en tres secciones:

```text
Registradas | Buscar | Subir APK
```

- `Registradas`: muestra apps y versiones ya registradas, con huecos de comparación visibles.
- `Buscar`: mantiene la búsqueda de Google Play y los huecos de comparación visibles.
- `Subir APK`: se centra solo en importar APKs al servidor y refresca `Registradas` al finalizar.

La extracción de APKs instaladas queda documentada como mejora experimental: en Android 11+ puede requerir declarar visibilidad de paquetes (`<queries>` o `QUERY_ALL_PACKAGES`), y muchas apps instaladas desde bundles usan split APKs, por lo que no basta con subir siempre el APK base.

### Transacciones cortas y análisis MobSF paralelo

La comparación separa dos fases para evitar conexiones `idle in transaction` durante análisis largos:

1. Fase de registro: descarga/ingesta, extracción de metadatos, registro de `Application`/`AppVersion`, almacenamiento gestionado y `commit()` inmediato.
2. Fase MobSF: cada análisis marca `PENDING`, hace `commit()`, ejecuta MobSF sin una transacción abierta y al finalizar guarda `SUCCESS`/`ERROR` con otro `commit()`.

Con esto, una versión nueva aparece en `/api/apps/registered` antes de que termine MobSF y la app Android puede mostrar `Analizada: No`, `Análisis: En progreso`, `Analizada: Sí` o `Error en análisis` según `estado_mobsf`.

Configuración disponible:

```env
MOBSF_ANALYSIS_MODE=sync
MOBSF_MAX_PARALLEL_ANALYSES=2
```

`sync` mantiene el análisis secuencial. `parallel` lanza análisis en paralelo con sesiones SQLAlchemy independientes y límite `MOBSF_MAX_PARALLEL_ANALYSES`. Para la VM UVA se recomienda empezar con:

```env
MOBSF_ANALYSIS_MODE=parallel
MOBSF_MAX_PARALLEL_ANALYSES=2
```

Aunque la VM tenga 16 cores y 32 GB RAM, MobSF/JADX/SAST/apktool son los componentes pesados; subir demasiado la concurrencia puede empeorar tiempos por CPU/I/O.

Para verificar que no quedan transacciones largas mientras MobSF analiza:

```sql
SELECT
    pid,
    usename,
    state,
    now() - xact_start AS transaction_age,
    now() - query_start AS query_age,
    wait_event_type,
    wait_event,
    LEFT(query, 300) AS query
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY xact_start NULLS LAST;
```
