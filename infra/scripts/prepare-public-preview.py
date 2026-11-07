#!/usr/bin/env python3
"""Prepare an opt-in HTTPS preview from the unchanged local test configuration.

No deployment, ports, DNS, certificate requests, identities or database changes.
Never print rendered configurations: they contain the existing OIDC signing key.
This is not a real-user, SMTP or production provisioning tool.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra" / "local"
APP_ORIGIN = "https://cockpit.investalo.de"
IDP_ORIGIN = "https://auth.cockpit.investalo.de"


def read_owned(path: Path, uid: int, mode: int, maximum: int = 65_536) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_nlink != 1 \
                or stat.S_IMODE(info.st_mode) != mode or info.st_size > maximum:
            raise RuntimeError("Unexpected protected file ownership, mode or size.")
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = -1
            return stream.read(maximum + 1)
    finally:
        if descriptor != -1:
            os.close(descriptor)


def directory(path: Path, uid: int) -> None:
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid \
                or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError("Unexpected preview directory ownership or mode.")
    else:
        os.chown(path, uid, uid)


def render(template: str, source: str) -> str:
    # Match the whole trusted template, allowing only bootstrap's two inserts.
    pattern = re.escape(template).replace(
        re.escape("@OIDC_SIGNING_KEY@"),
        r"(?P<signing>          -----BEGIN PRIVATE KEY-----\n"
        r"(?:          [A-Za-z0-9+/=]{1,64}\n)+"
        r"          -----END PRIVATE KEY-----)"
    ).replace(
        re.escape("@OIDC_CLIENT_HASH@"),
        r'(?P<client>"\$argon2id\$v=19\$m=[0-9]+,t=[0-9]+,p=[0-9]+'
        r'\$[A-Za-z0-9+/]+\$[A-Za-z0-9+/]+")'
    )
    matched = re.fullmatch(pattern, source)
    if not matched:
        raise RuntimeError("Local identity configuration drift; review it manually.")
    preview = template.replace(
        "# Rendered only for isolated local development. Never use this test identity/notifier\n"
        "# in the public pilot. Sensitive strings are supplied as per-service file secrets.",
        "# Prepared HTTPS preview using the existing synthetic identity and file notifier.\n"
        "# Real-user pilot/SMTP/recovery remain unapproved and unprovisioned."
    )
    for old, new in (
        ("https://auth.cockpit.local.test:8443", IDP_ORIGIN),
        ("https://cockpit.local.test:8443", APP_ORIGIN),
        ("auth.cockpit.local.test", "auth.cockpit.investalo.de"),
        ("cockpit.local.test", "cockpit.investalo.de"),
        ("Investalo Local Test", "Investalo HTTPS Preview"),
        ("Investalo Local Cockpit", "Investalo HTTPS Preview"),
    ):
        preview = preview.replace(old, new)
    return preview.replace("@OIDC_SIGNING_KEY@", matched["signing"]).replace(
        "@OIDC_CLIENT_HASH@", matched["client"]
    )


def create_config(path: Path, value: str) -> None:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    except FileExistsError:
        if read_owned(path, 10004, 0o400) != value:
            raise RuntimeError("Existing preview config differs; kept unchanged.")
        return
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            stream.write(value)
            stream.flush()
            os.fchown(stream.fileno(), 10004, 10004)
            os.fsync(stream.fileno())
    finally:
        if descriptor != -1:
            os.close(descriptor)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-preview", action="store_true", required=True,
                        help="Prepare only the existing synthetic development setup.")
    parser.parse_args(argv)
    if os.geteuid() != 0:
        raise RuntimeError("Requires root for service-specific file ownership.")
    info = LOCAL.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 \
            or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError("Requires the protected local bootstrap directory.")
    read_owned(LOCAL / "READY", 0, 0o400)
    source = read_owned(LOCAL / "authelia.yml", 10004, 0o400)
    users = read_owned(LOCAL / "users.yml", 10004, 0o400)
    if not re.fullmatch(
        r"users:\n  pilot:\n    disabled: false\n"
        r"    displayname: 'Lokaler Testnutzer'\n"
        r'    password: "\$argon2id\$[^"\r\n]+"\n'
        r"    email: 'pilot@example.invalid'\n    groups: \['invited'\]\n", users
    ):
        raise RuntimeError("Requires unchanged synthetic users; no real-user preparation.")
    template = (ROOT / "infra/authelia/configuration.template.yml").read_text()
    preview = render(template, source)
    directory(LOCAL / "caddy-public-data", 10001)
    directory(LOCAL / "cockpit-public-data", 10002)
    create_config(LOCAL / "authelia-public-preview.yml", preview)
    print("Protected preview configuration prepared; local configuration kept unchanged.")
    print("No deployment, identity provisioning, DNS or certificate request performed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, UnicodeError):
        # Exception text from IO/rendering may contain private paths or material.
        print("Preview preparation rejected; inspect ownership/configuration locally.", file=sys.stderr)
        sys.exit(1)
