#!/usr/bin/env bash
set -euo pipefail

project_name="aws-glue-postgres-mongodb-lab"
repo_root="/opt/$project_name"
key_dir="$HOME/.ssh/$project_name"
private_key="$key_dir/id_ed25519"
public_key="$key_dir/id_ed25519.pub"

if [[ "$(id -un)" != "ec2-user" ]]; then
  printf 'ERROR: run this script as ec2-user through SSM.\n' >&2
  exit 1
fi
install -d -m 700 "$key_dir"
if [[ ! -f "$private_key" ]]; then
  ssh-keygen -t ed25519 -N '' -C "$project_name-ec2-deploy-key" -f "$private_key" >/dev/null
fi
chmod 600 "$private_key"
chmod 644 "$public_key"

printf 'Add this public key as a write-enabled deploy key on Korrojo/%s:\n' "$project_name"
cat "$public_key"
printf '\nThe private key remains on EC2 at %s and was not printed.\n' "$private_key"

if [[ "${CONFIGURE_REMOTE:-0}" == "1" ]]; then
  git -C "$repo_root" remote set-url origin "git@github.com:Korrojo/$project_name.git"
  printf 'Configured the aws-glue-postgres-mongodb-lab origin for SSH.\n'
fi
