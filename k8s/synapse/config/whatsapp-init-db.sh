#!/bin/sh
set -eu

export PGPASSWORD="$POSTGRES_PASSWORD"

if psql -h synapse-db -U synapse -tc \
  "SELECT 1 FROM pg_roles WHERE rolname = 'mautrix_whatsapp'" | grep -q 1; then
  psql -h synapse-db -U synapse \
    -v ON_ERROR_STOP=1 \
    -v bridge_password="$MAUTRIX_POSTGRES_PASSWORD" <<'SQL'
ALTER USER mautrix_whatsapp WITH PASSWORD :'bridge_password';
SQL
else
  psql -h synapse-db -U synapse \
    -v ON_ERROR_STOP=1 \
    -v bridge_password="$MAUTRIX_POSTGRES_PASSWORD" <<'SQL'
CREATE USER mautrix_whatsapp WITH PASSWORD :'bridge_password';
SQL
fi

psql -h synapse-db -U synapse -tc \
  "SELECT 1 FROM pg_database WHERE datname = 'mautrix_whatsapp'" | grep -q 1 || \
  psql -h synapse-db -U synapse -c \
    "CREATE DATABASE mautrix_whatsapp OWNER mautrix_whatsapp;"

echo "WhatsApp bridge database initialization complete"
