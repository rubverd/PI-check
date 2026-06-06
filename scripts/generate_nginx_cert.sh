#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${OUT_DIR:-nginx/certs}"
SERVER_CN="${SERVER_CN:-virtual.lab.inf.uva.es}"
DAYS="${DAYS:-825}"
SAN_LIST="${SAN_LIST:-DNS:localhost,DNS:virtual.lab.inf.uva.es,IP:127.0.0.1,IP:10.0.20.49,IP:157.88.125.240}"

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"

CA_KEY="$OUT_DIR/picheck_ca.key"
CA_CRT="$OUT_DIR/picheck_ca.crt"
SERVER_KEY="$OUT_DIR/picheck-server.key"
SERVER_CSR="$OUT_DIR/picheck-server.csr"
SERVER_CRT="$OUT_DIR/picheck-server.crt"
OPENSSL_CNF="$OUT_DIR/picheck-server.openssl.cnf"

cat >&2 <<'WARN'
[WARNING] Este script genera claves privadas y certificados locales.
[WARNING] No subas al repositorio .env, picheck_ca.key, picheck-server.key ni certificados reales sensibles.
WARN

cat > "$OPENSSL_CNF" <<EOF
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
subjectAltName = $SAN_LIST

[cert_ext]
subjectAltName = $SAN_LIST
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF

if [[ ! -f "$CA_KEY" || ! -f "$CA_CRT" ]]; then
  openssl genrsa -out "$CA_KEY" 4096
  openssl req -x509 -new -nodes -key "$CA_KEY" -sha256 -days 3650 \
    -subj "/CN=PI-check Local CA/O=PI-check" -out "$CA_CRT"
fi

openssl genrsa -out "$SERVER_KEY" 4096
openssl req -new -key "$SERVER_KEY" -out "$SERVER_CSR" -config "$OPENSSL_CNF"
openssl x509 -req -in "$SERVER_CSR" -CA "$CA_CRT" -CAkey "$CA_KEY" -CAcreateserial \
  -out "$SERVER_CRT" -days "$DAYS" -sha256 -extensions cert_ext -extfile "$OPENSSL_CNF"

chmod 600 "$CA_KEY" "$SERVER_KEY"
chmod 644 "$CA_CRT" "$SERVER_CRT"

cat <<EOF
Certificados generados en $OUT_DIR:
- CA pública: $CA_CRT
- Certificado servidor nginx: $SERVER_CRT
- Clave privada servidor nginx: $SERVER_KEY

Ejemplo con SAN personalizados:
SAN_LIST="DNS:localhost,DNS:virtual.lab.inf.uva.es,IP:127.0.0.1,IP:10.0.20.49,IP:157.88.125.240" $0
EOF
