#!/usr/bin/env bash
set -euo pipefail

mongosh --quiet \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin <<'MONGOSH'
const target = db.getSiblingDB(process.env.MONGO_DATABASE);
target.createUser({
  user: process.env.MONGO_GLUE_USERNAME,
  pwd: process.env.MONGO_GLUE_PASSWORD,
  roles: [{ role: "readWrite", db: process.env.MONGO_DATABASE }],
});
target.createCollection("orders");
MONGOSH
