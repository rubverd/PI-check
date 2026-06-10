#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Bootstrap PI-check deployment assets for a fresh clone.

Creates/updates local-only deployment files:
  - .env (from .env.example when missing)
  - backend artifact directories
  - persistent CA in ~/.picheck/certs
  - nginx server certificate signed by that CA
  - Android public CA copy at mobile/app/src/main/res/raw/picheck_ca.crt

Defaults are safe development defaults, not real secrets:
  POSTGRES_PASSWORD=picheck
  MOBSF_API_KEY=picheck
  PICHECK_HTTPS_PORT=8443

Usage examples:
  ./scripts/bootstrap_deploy.sh
  ./scripts/bootstrap_deploy.sh --force-env
  PUBLIC_DNS="virtual.lab.inf.uva.es" PUBLIC_IP="157.88.125.240" VM_IP="10.0.20.49" \
    PICHECK_HTTPS_PORT="8443" POSTGRES_PASSWORD="picheck" MOBSF_API_KEY="picheck" \
    ./scripts/bootstrap_deploy.sh --force-env

Options:
  --force-env        Update .env even if it already exists, without prompting.
  --skip-env         Do not create or update .env.
  --help             Show this help.

Useful variables:
  PUBLIC_DNS, PUBLIC_IP, VM_IP, PICHECK_HTTPS_PORT, PICHECK_PUBLIC_BASE_URL, POSTGRES_PASSWORD, MOBSF_API_KEY
  POSTGRES_USER, POSTGRES_DB, MAX_UPLOAD_APK_SIZE_MB, CA_DIR, CERT_DAYS, SERVER_CN, EXTRA_DNS, EXTRA_IP, SAN_LIST
USAGE
}

FORCE_ENV="${FORCE_ENV:-false}"
SKIP_ENV="${SKIP_ENV:-false}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-env)
      FORCE_ENV="true"
      ;;
    --skip-env)
      SKIP_ENV="true"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PUBLIC_DNS="${PUBLIC_DNS:-virtual.lab.inf.uva.es}"
PUBLIC_IP="${PUBLIC_IP:-157.88.125.240}"
VM_IP="${VM_IP:-10.0.20.49}"
PICHECK_HTTPS_PORT="${PICHECK_HTTPS_PORT:-8443}"
PICHECK_PUBLIC_BASE_URL="${PICHECK_PUBLIC_BASE_URL:-https://${PUBLIC_DNS}:${PICHECK_HTTPS_PORT}}"
POSTGRES_USER="${POSTGRES_USER:-picheck}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-picheck}"
POSTGRES_DB="${POSTGRES_DB:-picheck}"
MOBSF_API_KEY="${MOBSF_API_KEY:-picheck}"
MAX_UPLOAD_APK_SIZE_MB="${MAX_UPLOAD_APK_SIZE_MB:-300}"
CERT_DAYS="${CERT_DAYS:-825}"
SERVER_CN="${SERVER_CN:-$PUBLIC_DNS}"
CA_DIR="${CA_DIR:-$HOME/.picheck/certs}"

ARTIFACT_DIRS=(
  "backend/artifacts/manual_uploads"
  "backend/artifacts/tmp/apks"
  "backend/artifacts/tmp/uploads"
  "backend/artifacts/apks"
  "backend/artifacts/comparisons"
  "backend/artifacts/reports/mobsf"
  "backend/artifacts/reports/mastg"
  "backend/artifacts/reports/comparisons"
  "nginx/certs"
  "mobile/app/src/main/res/raw"
)

for dir in "${ARTIFACT_DIRS[@]}"; do
  mkdir -p "$dir"
done

mkdir -p "$CA_DIR"
chmod 700 "$CA_DIR"

CA_KEY="$CA_DIR/picheck_ca.key"
CA_CRT="$CA_DIR/picheck_ca.crt"
CA_SRL="$CA_DIR/picheck_ca.srl"

if [[ -f "$CA_KEY" && -f "$CA_CRT" ]]; then
  echo "[CERT] Reusing persistent CA from $CA_DIR"
else
  echo "[CERT] Creating persistent CA in $CA_DIR"
  openssl genrsa -out "$CA_KEY" 4096
  openssl req -x509 -new -nodes -key "$CA_KEY" -sha256 -days 3650 \
    -subj "/CN=PI-check Local CA/O=PI-check" -out "$CA_CRT"
  chmod 600 "$CA_KEY"
  chmod 644 "$CA_CRT"
fi

install -m 644 "$CA_CRT" "nginx/certs/picheck_ca.crt"
install -m 644 "$CA_CRT" "mobile/app/src/main/res/raw/picheck_ca.crt"

if [[ -n "${SAN_LIST:-}" ]]; then
  SAN_VALUE="$SAN_LIST"
else
  SAN_ENTRIES=(
    "DNS:localhost"
    "DNS:$PUBLIC_DNS"
    "IP:127.0.0.1"
    "IP:$VM_IP"
    "IP:$PUBLIC_IP"
  )

  if [[ -n "${EXTRA_DNS:-}" ]]; then
    IFS=',' read -ra EXTRA_DNS_VALUES <<< "$EXTRA_DNS"
    for dns in "${EXTRA_DNS_VALUES[@]}"; do
      [[ -n "$dns" ]] && SAN_ENTRIES+=("DNS:$dns")
    done
  fi

  if [[ -n "${EXTRA_IP:-}" ]]; then
    IFS=',' read -ra EXTRA_IP_VALUES <<< "$EXTRA_IP"
    for ip in "${EXTRA_IP_VALUES[@]}"; do
      [[ -n "$ip" ]] && SAN_ENTRIES+=("IP:$ip")
    done
  fi

  SAN_VALUE="$(IFS=','; echo "${SAN_ENTRIES[*]}")"
fi

SERVER_KEY="nginx/certs/picheck-server.key"
SERVER_CSR="nginx/certs/picheck-server.csr"
SERVER_CRT="nginx/certs/picheck-server.crt"
SERVER_CNF="nginx/certs/picheck-server.cnf"

cat > "$SERVER_CNF" <<EOF_CNF
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
CN = $SERVER_CN
O = PI-check Local

[req_ext]
subjectAltName = $SAN_VALUE

[cert_ext]
subjectAltName = $SAN_VALUE
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF_CNF

openssl genrsa -out "$SERVER_KEY" 4096
openssl req -new -key "$SERVER_KEY" -out "$SERVER_CSR" -config "$SERVER_CNF"
openssl x509 -req -in "$SERVER_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" \
  -CAserial "$CA_SRL" -CAcreateserial -out "$SERVER_CRT" -days "$CERT_DAYS" \
  -sha256 -extensions cert_ext -extfile "$SERVER_CNF"
chmod 600 "$SERVER_KEY"
chmod 644 "$SERVER_CRT" "$SERVER_CNF"
rm -f "$SERVER_CSR"

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  local escaped
  escaped="$(printf '%s' "$value" | sed 's/[&/\\]/\\&/g')"

  if grep -qE "^${key}=" "$file"; then
    sed -i "s/^${key}=.*/${key}=${escaped}/" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

if [[ "$SKIP_ENV" != "true" ]]; then
  ENV_FILE=".env"
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "[ENV] Creating .env from .env.example"
    cp .env.example "$ENV_FILE"
    UPDATE_ENV="true"
  elif [[ "$FORCE_ENV" == "true" ]]; then
    echo "[ENV] Updating existing .env because --force-env/FORCE_ENV=true was provided"
    cp "$ENV_FILE" ".env.backup.$(date +%Y%m%d%H%M%S)"
    UPDATE_ENV="true"
  elif [[ -t 0 ]]; then
    read -r -p "[ENV] .env already exists. Update managed values? [y/N] " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
      cp "$ENV_FILE" ".env.backup.$(date +%Y%m%d%H%M%S)"
      UPDATE_ENV="true"
    else
      UPDATE_ENV="false"
    fi
  else
    echo "[ENV] .env already exists; not modifying it without --force-env in non-interactive mode."
    UPDATE_ENV="false"
  fi

  if [[ "$UPDATE_ENV" == "true" ]]; then
    DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"
    set_env_value "$ENV_FILE" "POSTGRES_USER" "$POSTGRES_USER"
    set_env_value "$ENV_FILE" "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
    set_env_value "$ENV_FILE" "POSTGRES_DB" "$POSTGRES_DB"
    set_env_value "$ENV_FILE" "DATABASE_URL" "$DATABASE_URL"
    set_env_value "$ENV_FILE" "MOBSF_API_KEY" "$MOBSF_API_KEY"
    set_env_value "$ENV_FILE" "PICHECK_HTTPS_PORT" "$PICHECK_HTTPS_PORT"
    set_env_value "$ENV_FILE" "PICHECK_PUBLIC_BASE_URL" "$PICHECK_PUBLIC_BASE_URL"
    set_env_value "$ENV_FILE" "APK_STORAGE_DIR" "/app/artifacts/apks"
    set_env_value "$ENV_FILE" "APK_UPLOAD_STAGING_DIR" "/app/artifacts/tmp/uploads"
    set_env_value "$ENV_FILE" "MAX_UPLOAD_APK_SIZE_MB" "$MAX_UPLOAD_APK_SIZE_MB"
    set_env_value "$ENV_FILE" "MOBSF_ANALYSIS_MODE" "${MOBSF_ANALYSIS_MODE:-sync}"
    set_env_value "$ENV_FILE" "MOBSF_MAX_PARALLEL_ANALYSES" "${MOBSF_MAX_PARALLEL_ANALYSES:-2}"
    set_env_value "$ENV_FILE" "COMPARISON_ARTIFACTS_DIR" "/app/artifacts/comparisons"
  fi
else
  echo "[ENV] Skipping .env creation/update because --skip-env/SKIP_ENV=true was provided"
fi

cat <<EOF_DONE

[OK] PI-check bootstrap completed.

Generated/reused local-only files:
- Persistent CA private key: $CA_KEY (do not commit)
- Persistent CA public cert: $CA_CRT
- nginx public CA copy: nginx/certs/picheck_ca.crt
- Android public CA copy: mobile/app/src/main/res/raw/picheck_ca.crt
- nginx server cert: $SERVER_CRT
- nginx server key: $SERVER_KEY (do not commit)
- nginx server config: $SERVER_CNF

SAN used for nginx certificate:
$SAN_VALUE

Next steps:
1. Review .env if it was created/updated.
2. Run: docker compose config
3. Run: docker compose build && docker compose up -d
4. Run: docker compose exec backend alembic upgrade head

If the CA changed, rebuild and reinstall the Android app so it trusts the new nginx certificate.
EOF_DONE
