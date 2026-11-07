#!/usr/bin/env python3
"""Create isolated development secrets/certificates; never print their values.

This deliberately provisions a .invalid test identity and filesystem notifier.
It is not a production provisioning or recovery tool.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra" / "local"
AUTHELIA_UID = 10004
SHARED_GID = 10010


def write(path: Path, value: str, *, uid: int = 0, gid: int = 0,
          mode: int = 0o400) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def run(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        # Tool output can contain generated keys or passwords. Never echo it.
        raise RuntimeError(f"Local provisioning tool failed: {args[0]}")
    return result.stdout


def random_hash(image: str) -> tuple[str, str]:
    output = run(
        "docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--user", "10004:10004",
        image, "authelia", "crypto", "hash", "generate", "argon2",
        "--random", "--random.length", "48", "--parallelism", "2",
    )
    digest = re.search(r"(\$argon2id\$v=19\$[^\s]+)", output)
    password = re.search(r"(?:Random Password|Password):\s*(\S+)", output,
                         flags=re.IGNORECASE)
    if not digest or not password:
        raise RuntimeError("Cannot parse Authelia generated credentials.")
    return password.group(1), digest.group(1)


def certificate(name: str, domains: tuple[str, ...], uid: int) -> None:
    key = LOCAL / f"{name}_tls_key"
    csr = LOCAL / f"{name}.csr"
    cert = LOCAL / f"{name}_tls_cert"
    extension = LOCAL / f"{name}.extensions"
    run("openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
        "rsa_keygen_bits:3072", "-out", str(key))
    run("openssl", "req", "-new", "-key", str(key), "-out", str(csr),
        "-subj", f"/CN={domains[0]}")
    write(extension, "basicConstraints=critical,CA:FALSE\n"
          "keyUsage=critical,digitalSignature,keyEncipherment\n"
          "extendedKeyUsage=serverAuth\nsubjectAltName="
          + ",".join(f"DNS:{name}" for name in domains) + "\n")
    run("openssl", "x509", "-req", "-in", str(csr),
        "-CA", str(LOCAL / "local_ca_cert"),
        "-CAkey", str(LOCAL / "local_ca_key"),
        "-set_serial", str(secrets.randbits(128)), "-days", "90",
        "-sha256", "-extfile", str(extension), "-out", str(cert))
    os.chown(key, uid, uid)
    os.chmod(key, 0o400)
    os.chmod(cert, 0o444)


def main() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("Run as root to assign service-specific file owners.")
    if LOCAL.exists():
        if (LOCAL / "READY").exists():
            print("Local development material already exists; kept unchanged.")
            return
        raise RuntimeError("Partial local directory exists; inspect it first.")
    os.umask(0o077)
    LOCAL.mkdir(mode=0o700)
    images = dict(
        line.split("=", 1) for line in
        (ROOT / "infra" / "images.env").read_text().splitlines()
        if line and not line.startswith("#")
    )
    password, password_hash = random_hash(images["AUTHELIA_IMAGE"])
    client_secret, client_hash = random_hash(images["AUTHELIA_IMAGE"])

    owners = {
        "postgres_admin_password": (999, 999, 0o400),
        "platform_migration_password": (10003, 10003, 0o400),
        "platform_runtime_password": (10003, 10003, 0o400),
        "authelia_db_password": (AUTHELIA_UID, AUTHELIA_UID, 0o400),
        "internal_api_key": (0, SHARED_GID, 0o440),
        "cockpit_session_key": (10002, 10002, 0o400),
        "authelia_session_secret": (AUTHELIA_UID, AUTHELIA_UID, 0o400),
        "authelia_storage_key": (AUTHELIA_UID, AUTHELIA_UID, 0o400),
        "authelia_oidc_hmac_secret": (AUTHELIA_UID, AUTHELIA_UID, 0o400),
        "authelia_reset_jwt_secret": (AUTHELIA_UID, AUTHELIA_UID, 0o400),
    }
    for name, (uid, gid, mode) in owners.items():
        value = secrets.token_urlsafe(48)
        write(LOCAL / name, value, uid=uid, gid=gid,
              mode=mode)
        if name in {"platform_migration_password", "platform_runtime_password",
                    "authelia_db_password"}:
            # Initialization-only copies: PostgreSQL cannot read another
            # runtime's private file, and other services never mount these.
            write(LOCAL / f"bootstrap_{name}", value, uid=999, gid=999)
    write(LOCAL / "oidc_client_secret", client_secret, uid=10002, gid=10002)
    write(LOCAL / "pilot-access.txt",
          "LOCAL TEST IDENTITY ONLY — no external email delivery\n"
          "Username: pilot\nEmail: pilot@example.invalid\n"
          f"Password: {password}\n", mode=0o600)
    write(LOCAL / "users.yml", f"""users:
  pilot:
    disabled: false
    displayname: 'Lokaler Testnutzer'
    password: {json.dumps(password_hash)}
    email: 'pilot@example.invalid'
    groups: ['invited']
""", uid=AUTHELIA_UID, gid=AUTHELIA_UID)

    run("openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
        "rsa_keygen_bits:3072", "-out", str(LOCAL / "local_ca_key"))
    run("openssl", "req", "-x509", "-new", "-sha256", "-days", "365",
        "-key", str(LOCAL / "local_ca_key"), "-out",
        str(LOCAL / "local_ca_cert"), "-subj", "/CN=Investalo Local Dev CA",
        "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    os.chmod(LOCAL / "local_ca_key", 0o400)
    os.chmod(LOCAL / "local_ca_cert", 0o444)
    certificate("ingress", ("cockpit.local.test", "auth.cockpit.local.test"), 10001)
    certificate("postgres", ("postgres",), 999)
    certificate("api", ("api",), 10003)
    certificate("authelia", ("authelia",), AUTHELIA_UID)
    run("openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
        "rsa_keygen_bits:3072", "-out", str(LOCAL / "oidc_signing_key"))
    signing_key = (LOCAL / "oidc_signing_key").read_text().strip()
    os.chmod(LOCAL / "oidc_signing_key", 0o400)
    template = (ROOT / "infra" / "authelia" / "configuration.template.yml").read_text()
    config = template.replace("@OIDC_CLIENT_HASH@", json.dumps(client_hash))
    config = config.replace("@OIDC_SIGNING_KEY@", "\n".join(
        "          " + line for line in signing_key.splitlines()
    ))
    write(LOCAL / "authelia.yml", config, uid=AUTHELIA_UID, gid=AUTHELIA_UID)
    # Host bind directories are explicit and owned by their nonroot runtimes.
    for name, uid in (("postgres-data", 999), ("authelia-data", AUTHELIA_UID),
                      ("cockpit-data", 10002), ("caddy-data", 10001)):
        path = LOCAL / name
        path.mkdir(mode=0o700)
        os.chown(path, uid, uid)
    write(LOCAL / "READY", "Local test material initialized.\n")
    print("Local development secrets and TLS certificates created in infra/local/.")
    print("Test access is in the protected pilot-access.txt; values were not logged.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
