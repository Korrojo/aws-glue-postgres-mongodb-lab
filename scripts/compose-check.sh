#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v docker >/dev/null 2>&1 || {
  printf 'ERROR: docker is required for Compose validation.\n' >&2
  exit 2
}
command -v openssl >/dev/null 2>&1 || {
  printf 'ERROR: openssl is required to generate throwaway validation values.\n' >&2
  exit 2
}
umask 077
temp_env="$(mktemp)"
trap 'rm -f "$temp_env"' EXIT

{
  printf 'DATABASE_BIND_ADDRESS=127.0.0.1\n'
  printf 'POSTGRES_DB=sales_lab\n'
  printf 'POSTGRES_USER=lab_admin\n'
  printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  printf 'MONGO_INITDB_ROOT_USERNAME=lab_root\n'
  printf 'MONGO_INITDB_ROOT_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  printf 'MONGO_DATABASE=migration_lab\n'
  printf 'MONGO_GLUE_USERNAME=glue_writer\n'
  printf 'MONGO_GLUE_PASSWORD=%s\n' "$(openssl rand -hex 24)"
} >"$temp_env"

docker compose \
  --env-file "$temp_env" \
  -f "$repo_root/docker/compose.yaml" \
  config --quiet
