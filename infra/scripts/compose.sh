#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec docker compose --project-name investalo-local \
  --env-file "${repo_dir}/infra/images.env" \
  --file "${repo_dir}/infra/compose.yaml" "$@"
