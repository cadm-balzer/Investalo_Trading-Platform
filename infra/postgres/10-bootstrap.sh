#!/usr/bin/env bash
# Invoked by the stock PostgreSQL entrypoint, explicitly running as uid 999.
# File-backed credentials never enter a process argument, shell trace or output.
set -euo pipefail

platform_migration_password="$(cat /run/secrets/bootstrap_platform_migration_password)"
platform_runtime_password="$(cat /run/secrets/bootstrap_platform_runtime_password)"
identity_password="$(cat /run/secrets/bootstrap_authelia_db_password)"
export platform_migration_password platform_runtime_password identity_password
psql --username "${POSTGRES_USER}" --dbname postgres --no-psqlrc \
  --set ON_ERROR_STOP=1 <<'SQL'
\getenv migration_password platform_migration_password
\getenv runtime_password platform_runtime_password
\getenv identity_password identity_password
SET password_encryption = 'scram-sha-256';
CREATE ROLE investalo_migration LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'migration_password';
CREATE ROLE investalo_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'runtime_password';
CREATE ROLE investalo_identity LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'identity_password';
CREATE DATABASE investalo OWNER investalo_migration;
CREATE DATABASE investalo_identity OWNER investalo_identity;
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
REVOKE ALL ON DATABASE investalo FROM PUBLIC;
REVOKE ALL ON DATABASE investalo_identity FROM PUBLIC;
GRANT CONNECT ON DATABASE investalo TO investalo_runtime;
\connect investalo
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO investalo_migration;
GRANT USAGE ON SCHEMA public TO investalo_runtime;
\connect investalo_identity
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO investalo_identity;
SQL
