#!/bin/sh
set -eu

export PGPASSWORD="$POSTGRES_PASSWORD"

if psql -h synapse-db -U synapse -tc \
  "SELECT 1 FROM pg_roles WHERE rolname = 'mautrix_signal'" | grep -q 1; then
  psql -h synapse-db -U synapse \
    -v ON_ERROR_STOP=1 \
    -v bridge_password="$MAUTRIX_POSTGRES_PASSWORD" <<'SQL'
ALTER USER mautrix_signal WITH PASSWORD :'bridge_password';
SQL
else
  psql -h synapse-db -U synapse \
    -v ON_ERROR_STOP=1 \
    -v bridge_password="$MAUTRIX_POSTGRES_PASSWORD" <<'SQL'
CREATE USER mautrix_signal WITH PASSWORD :'bridge_password';
SQL
fi

psql -h synapse-db -U synapse -tc \
  "SELECT 1 FROM pg_database WHERE datname = 'mautrix_signal'" | grep -q 1 || \
  psql -h synapse-db -U synapse -c \
    "CREATE DATABASE mautrix_signal OWNER mautrix_signal;"

echo "Signal bridge database initialization complete"
