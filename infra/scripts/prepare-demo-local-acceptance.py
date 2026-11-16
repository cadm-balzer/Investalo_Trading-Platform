#!/usr/bin/env python3
"""Prepare only the protected synthetic Demo acceptance directory, without keys."""
import os
from pathlib import Path
import stat

ROOT = Path("/tmp/investalo-demo-local-acceptance")
MARKER = ".synthetic-demo-acceptance"
CONTENT = b"investalo-synthetic-demo-local-acceptance/1\n"


def main():
    if os.geteuid() != 0:
        raise ValueError()
    parent = os.open("/tmp", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    descriptor = None
    try:
        created = False
        try:
            os.mkdir(ROOT.name, mode=0o700, dir_fd=parent)
            created = True
        except FileExistsError:
            pass
        descriptor = os.open(ROOT.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        if created:
            marker = os.open(MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=descriptor)
            try:
                if os.write(marker, CONTENT) != len(CONTENT):
                    raise ValueError()
                os.fchown(marker, 10003, 10003)
                os.fsync(marker)
            finally:
                os.close(marker)
            os.fchown(descriptor, 10003, 10003)
            os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        linked = os.stat(ROOT.name, dir_fd=parent, follow_symlinks=False)
        if (not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700
                or metadata.st_uid != 10003 or metadata.st_gid != 10003
                or (metadata.st_dev, metadata.st_ino) != (linked.st_dev, linked.st_ino)):
            raise ValueError()
        marker = os.open(MARKER, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        try:
            metadata = os.fstat(marker)
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 10003 or metadata.st_gid != 10003
                    or stat.S_IMODE(metadata.st_mode) != 0o400 or metadata.st_nlink != 1
                    or os.read(marker, len(CONTENT) + 1) != CONTENT):
                raise ValueError()
        finally:
            os.close(marker)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)
    print("PASS: protected synthetic Demo acceptance root verified")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Synthetic Demo acceptance root rejected") from None
