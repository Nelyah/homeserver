#!/bin/sh
set -e
export PGPASSWORD=$POSTGRES_PASSWORD

# Create user if not exists, or update password if exists
psql -h synapse_db -U synapse -tc \
  "SELECT 1 FROM pg_roles WHERE rolname = 'mautrix_whatsapp'" | grep -q 1 && \
  psql -h synapse_db -U synapse -c \
    "ALTER USER mautrix_whatsapp WITH PASSWORD '$MAUTRIX_POSTGRES_PASSWORD';" || \
  psql -h synapse_db -U synapse -c \
    "CREATE USER mautrix_whatsapp WITH PASSWORD '$MAUTRIX_POSTGRES_PASSWORD';"

# Create database if not exists
psql -h synapse_db -U synapse -tc \
  "SELECT 1 FROM pg_database WHERE datname = 'mautrix_whatsapp'" | grep -q 1 || \
  psql -h synapse_db -U synapse -c \
    "CREATE DATABASE mautrix_whatsapp OWNER mautrix_whatsapp;"

echo "Database initialization complete"
