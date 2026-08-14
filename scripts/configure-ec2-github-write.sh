#!/usr/bin/env bash
set -euo pipefail

project_name="aws-glue-postgres-mongodb-lab"
repo_root="/opt/$project_name"
key_dir="$HOME/.ssh/$project_name"
private_key="$key_dir/id_ed25519"
public_key="$key_dir/id_ed25519.pub"
known_hosts="$key_dir/known_hosts"

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
  python3 - "$known_hosts" <<'PY'
import json
import pathlib
import sys
import urllib.request
request = urllib.request.Request(
    "https://api.github.com/meta",
    headers={"Accept": "application/vnd.github+json", "User-Agent": "aws-glue-lab"},
)
with urllib.request.urlopen(request, timeout=30) as response:
    metadata = json.load(response)
keys = metadata.get("ssh_keys", [])
if not keys:
    raise SystemExit("GitHub metadata returned no SSH host keys")
pathlib.Path(sys.argv[1]).write_text(
    "".join(f"github.com {key}\n" for key in keys)
)
PY
  chmod 600 "$known_hosts"
  ssh-keygen -F github.com -f "$known_hosts" >/dev/null
  git -C "$repo_root" config core.sshCommand \
    "ssh -i $private_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known_hosts"
  git -C "$repo_root" remote set-url origin "git@github.com:Korrojo/$project_name.git"
  printf 'Configured the aws-glue-postgres-mongodb-lab origin, deploy-key identity, and GitHub known_hosts for SSH.\n'
fi
