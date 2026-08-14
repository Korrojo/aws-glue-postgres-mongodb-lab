#!/usr/bin/env bash
# shellcheck disable=SC2016 # Single-quoted snippets expand only inside the containers.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose=(docker compose --env-file "$repo_root/.env" -f "$repo_root/docker/compose.yaml")

"${compose[@]}" exec -T postgres sh -ceu '
  psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --file /docker-entrypoint-initdb.d/02-seed.sql
' >/dev/null
"${compose[@]}" exec -T postgres sh -ceu '
  psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --file /docker-entrypoint-initdb.d/03-assert-valid.sql
'

for fixture_path in "$repo_root"/docker/postgres/invalid/*.sql; do
  fixture="/lab-invalid-fixtures/$(basename "$fixture_path")"
  if "${compose[@]}" exec -T postgres sh -ceu '
    psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file "$1"
  ' sh "$fixture" >/dev/null 2>&1; then
    printf 'ERROR: invalid fixture unexpectedly succeeded: %s\n' "$fixture" >&2
    exit 1
  fi
  printf 'expected rejection: %s\n' "$(basename "$fixture")"
done

mongo_count="$(
  "${compose[@]}" exec -T mongodb sh -ceu '
    mongosh --quiet \
      --username "$MONGO_GLUE_USERNAME" \
      --password "$MONGO_GLUE_PASSWORD" \
      --authenticationDatabase "$MONGO_DATABASE" \
      "$MONGO_DATABASE" \
      --eval "db.orders.countDocuments({})"
  '
)"
if [[ "$mongo_count" != "0" ]]; then
  printf 'ERROR: expected an empty MongoDB orders collection, got count=%s\n' "$mongo_count" >&2
  exit 1
fi

printf 'local data assertions: PASS\n'
