#!/usr/bin/env bash
# Pinned local development toolchain; no application ports or deployment.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root to install the verified Docker packages." >&2
  exit 1
fi
source /etc/os-release
if [[ "${ID}" != "ubuntu" || "${VERSION_CODENAME}" != "resolute" ]]; then
  echo "This installer is verified only for Ubuntu 26.04 (resolute)." >&2
  exit 1
fi
if [[ "$(dpkg --print-architecture)" != "amd64" ]]; then
  echo "Review exact package pins for this architecture first." >&2
  exit 1
fi
for conflict in docker.io docker-doc docker-compose docker-compose-v2 docker-buildx podman-docker containerd runc; do
  if dpkg-query -W -f='${db:Status-Status}' "${conflict}" 2>/dev/null |
    awk 'BEGIN { found=0 } $0 == "installed" { found=1 } END { exit !found }'; then
    echo "Conflicting package ${conflict}; no automatic removal." >&2
    exit 1
  fi
done

bootstrap_dir="$(mktemp -d /tmp/investalo-docker.XXXXXX)"
curl --fail --silent --show-error \
  https://download.docker.com/linux/ubuntu/gpg \
  --output "${bootstrap_dir}/docker.asc"
fingerprint="$(gpg --batch --show-keys --with-colons "${bootstrap_dir}/docker.asc" |
  awk -F: '$1 == "fpr" { print $10; exit }')"
if [[ "${fingerprint}" != "9DC858229FC7DD38854AE2D88D81803C0EBFCD88" ]]; then
  echo "Unexpected Docker signing-key fingerprint." >&2
  exit 1
fi
cat >"${bootstrap_dir}/docker.sources" <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: resolute
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF

if [[ -e /etc/apt/sources.list.d/docker.sources ]] &&
  ! cmp --silent "${bootstrap_dir}/docker.sources" /etc/apt/sources.list.d/docker.sources; then
  echo "Existing Docker source differs; refusing to overwrite it." >&2
  exit 1
fi
install -d -m 0755 /etc/apt/keyrings
install -m 0644 "${bootstrap_dir}/docker.asc" /etc/apt/keyrings/docker.asc
install -m 0644 "${bootstrap_dir}/docker.sources" /etc/apt/sources.list.d/docker.sources
apt-get update
env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l \
  apt-get install --yes --no-install-recommends \
  docker-ce=5:29.9.3-1~ubuntu.26.04~resolute \
  docker-ce-cli=5:29.9.3-1~ubuntu.26.04~resolute \
  containerd.io=2.4.2-3~ubuntu.26.04~resolute \
  docker-buildx-plugin=0.38.1-1~ubuntu.26.04~resolute \
  docker-compose-plugin=5.7.0-1~ubuntu.26.04~resolute \
  python3-venv=3.14.3-0ubuntu2
docker --version
docker compose version
docker buildx version
