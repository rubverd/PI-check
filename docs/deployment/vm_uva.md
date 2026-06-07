# Despliegue PI-check en VM UVA

Esta guía prepara el despliegue manual en la VM de la universidad. No contiene credenciales reales.

## Datos que deben confirmarse

* SSH: `virtual.lab.inf.uva.es:20491`.
* HTTPS público esperado: `https://virtual.lab.inf.uva.es:20492`.
* Confirmar con los técnicos si el forwarding público `20492` apunta a:
  * `10.0.20.49:8443`, o
  * `10.0.20.49:20492`.

## Puerto HTTPS interno

nginx dentro del contenedor debe seguir escuchando en `443 ssl`. `docker-compose.yml` publica nginx como `${PICHECK_HTTPS_PORT}:443`.

* Si `20492 -> 8443`, mantén en `.env`:
  ```env
  PICHECK_HTTPS_PORT=8443
  ```
* Si `20492 -> 20492`, usa:
  ```env
  PICHECK_HTTPS_PORT=20492
  ```

El backend FastAPI (`8088`) no debería exponerse públicamente. Debe quedar detrás de nginx; Compose lo publica en `127.0.0.1:${PICHECK_API_PORT}:8088` solo para pruebas locales en la VM.

## Preparación de `.env`

Copia `.env.example` a `.env` en la raíz del repo desplegado y cambia contraseñas/API keys:

```bash
cp .env.example .env
nano .env
```

No commitees `.env`.

## Carpeta para APKs manuales

En el host:

```bash
mkdir -p backend/artifacts/manual_uploads
```

Dentro del backend se monta como:

```text
/app/artifacts/manual_uploads
```

## Certificados nginx

Genera una CA local y certificado de servidor con SAN:

```bash
./scripts/generate_nginx_cert.sh
```

SAN por defecto incluidos:

* `DNS:localhost`
* `DNS:virtual.lab.inf.uva.es`
* `IP:127.0.0.1`
* `IP:10.0.20.49`
* `IP:157.88.125.240`

Para personalizar:

```bash
SAN_LIST="DNS:localhost,DNS:virtual.lab.inf.uva.es,IP:127.0.0.1,IP:10.0.20.49,IP:157.88.125.240" ./scripts/generate_nginx_cert.sh
```

No commitees `picheck_ca.key`, `picheck-server.key`, `.env` ni certificados reales sensibles.

## Android y CA propia

Si usas CA propia, copia `nginx/certs/picheck_ca.crt` a `mobile/app/src/main/res/raw/picheck_ca.crt`, recompila la app y revisa `network_security_config.xml`. En el cliente Android, la URL de VM esperada es:

```text
https://virtual.lab.inf.uva.es:20492
```

## Despliegue y migraciones

```bash
docker compose build
docker compose up -d
```

Aplica migraciones Alembic:

```bash
docker compose exec backend alembic upgrade head
```

## Pruebas

```bash
docker compose ps
curl -k https://localhost:${PICHECK_HTTPS_PORT}/api/apps/registered
```

Desde fuera de la universidad/VM:

```text
https://virtual.lab.inf.uva.es:20492/api/apps/registered
```

## Registro de APK local

Copia APK/XAPK/APKS/APKM al host en `backend/artifacts/manual_uploads` y llama al endpoint con la ruta del contenedor:

```bash
curl -k -X POST "https://localhost:${PICHECK_HTTPS_PORT}/api/apps/register-local-apk" \
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

## Operación manual pendiente en VM

1. Confirmar el forwarding real del puerto `20492`.
2. Crear `.env` real con secretos propios.
3. Generar/instalar certificados.
4. Copiar APKs del dataset a `backend/artifacts/manual_uploads`.
5. Levantar contenedores, aplicar migraciones y probar endpoints.
