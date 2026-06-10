#!/usr/bin/env bash
set -euo pipefail

# Bootstrap profile for the current UVA VM deployment.
# Public forwarding: virtual.lab.inf.uva.es:20492 -> VM:8443.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export PUBLIC_DNS="${PUBLIC_DNS:-virtual.lab.inf.uva.es}"
export PUBLIC_IP="${PUBLIC_IP:-157.88.125.240}"
export VM_IP="${VM_IP:-10.0.20.49}"
export PICHECK_HTTPS_PORT="${PICHECK_HTTPS_PORT:-8443}"
export PICHECK_PUBLIC_BASE_URL="${PICHECK_PUBLIC_BASE_URL:-https://virtual.lab.inf.uva.es:20492}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-picheck}"
export MOBSF_API_KEY="${MOBSF_API_KEY:-picheck}"

exec "$SCRIPT_DIR/bootstrap_deploy.sh" "$@"
