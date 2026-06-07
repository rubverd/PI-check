#!/usr/bin/env bash
set -euo pipefail

# Backwards-compatible certificate helper.
# Prefer scripts/bootstrap_deploy.sh for full deployment bootstrap. This wrapper only
# creates/reuses the persistent CA and regenerates nginx/Android certificate assets;
# it intentionally skips .env changes.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat >&2 <<'WARN'
[INFO] Delegating certificate generation to scripts/bootstrap_deploy.sh --skip-env.
[INFO] CA private key is kept under ~/.picheck/certs, not inside the repository.
[WARNING] Do not commit .env, picheck_ca.key, picheck-server.key, CSR/SRL files, APKs, or generated artifacts.
WARN

exec "$SCRIPT_DIR/bootstrap_deploy.sh" --skip-env "$@"
