#!/usr/bin/env python3
"""Prepare a single explicit platform administrator. No SMTP password intake."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra/local"


def write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, "wb") as stream:
        stream.write(value); stream.flush(); os.fsync(stream.fileno())
        os.fchown(stream.fileno(), 10002, 10002)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--smtp-host", required=True)
    args = parser.parse_args()
    try:
        if (os.geteuid() != 0 or not re.fullmatch(r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", args.recipient)
                or not re.fullmatch(r"[a-z0-9.-]{1,253}", args.smtp_host) or "." not in args.smtp_host):
            raise ValueError()
        path = LOCAL / "public-preview-identity.json"
        m = path.lstat()
        if not stat.S_ISREG(m.st_mode) or m.st_uid != 0 or stat.S_IMODE(m.st_mode) != 0o600 or m.st_nlink != 1:
            raise ValueError()
        actor = json.loads(path.read_bytes())
        if actor["issuer"] != "https://auth.cockpit.investalo.de":
            raise ValueError()
        directory = LOCAL / "platform-admin"
        for parent in directory.parents:
            if parent.is_symlink():
                raise ValueError()
        directory.mkdir(mode=0o700)
        key = secrets.token_bytes(32)
        config = dict(schema="investalo-platform-admin/1",
            tenantId=str(UUID(actor["tenant_id"])), userId=str(UUID(actor["user_id"])),
            subject=str(UUID(actor["subject"])), issuer=actor["issuer"],
            origin="https://cockpit.investalo.de", recipient=args.recipient,
            defaultHost=args.smtp_host, keySha256=hashlib.sha256(key).hexdigest())
        write(directory / "config", json.dumps(config, sort_keys=True).encode())
        write(directory / "smtp-key", key)
        os.chown(directory, 10002, 10002)
        print("Private platform administrator prepared. No SMTP password or running-service change.")
        return 0
    except Exception:
        print("Platform administrator setup rejected; private values suppressed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
