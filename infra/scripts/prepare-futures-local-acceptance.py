#!/usr/bin/env python3
"""Create only the dedicated synthetic local Futures acceptance mount."""
import os
import argparse
from pathlib import Path
import stat

ROOT = Path("/tmp/investalo-futures-local-acceptance")
MARKER = b"synthetic-local-futures-acceptance/1\n"


def main():
    global ROOT, MARKER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery", action="store_true")
    args = parser.parse_args()
    if args.recovery:
        ROOT = Path("/tmp/investalo-futures-recovery-acceptance")
        MARKER = b"synthetic-local-futures-recovery-acceptance/1\n"
    children = ("status", "registry") if args.recovery else ("status",)
    if os.geteuid() != 0:
        raise ValueError("root preparation required")
    parent = os.open("/tmp", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created = False
    try:
        try:
            os.mkdir(ROOT.name, 0o700, dir_fd=parent)
            created = True
        except FileExistsError:
            pass
        fd = os.open(ROOT.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if created:
                if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
                    raise ValueError("new acceptance directory drift")
                marker = os.open(".fixture", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o400, dir_fd=fd)
                with os.fdopen(marker, "wb") as stream:
                    stream.write(MARKER)
                    os.fchown(stream.fileno(), 10003, 10010)
                    os.fsync(stream.fileno())
                for name in children:
                    os.mkdir(name, 0o700, dir_fd=fd)
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        os.fchown(child, 10003, 10010)
                        os.fsync(child)
                    finally:
                        os.close(child)
                os.fchown(fd, 10003, 10010)
                os.fsync(fd)
                os.fsync(parent)
            info = os.fstat(fd)
            if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (10003, 10010, 0o700):
                raise ValueError("acceptance directory drift")
            marker = os.open(".fixture", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                info = os.fstat(marker)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or (info.st_uid, stat.S_IMODE(info.st_mode)) != (10003, 0o400)
                        or os.read(marker, 128) != MARKER):
                    raise ValueError("acceptance marker drift")
            finally:
                os.close(marker)
            for name in children:
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    info = os.fstat(child)
                    if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (10003, 10010, 0o700):
                        raise ValueError("acceptance child directory drift")
                finally:
                    os.close(child)
        finally:
            os.close(fd)
    finally:
        os.close(parent)
    print("PASS: dedicated synthetic Futures acceptance mount; existing artifacts retained")


if __name__ == "__main__":
    main()
