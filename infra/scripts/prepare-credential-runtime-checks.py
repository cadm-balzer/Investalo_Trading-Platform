#!/usr/bin/env python3
"""Prepare the fixed synthetic credential-service fixture directory, no keys."""
import os
from pathlib import Path
import stat

STATE = Path("/tmp/investalo-credential-runtime-state")
MARKER = ".investalo-credential-runtime-checks"
CONTENT = b"synthetic-credential-runtime-state-v1\n"
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def verify_binding(parent_fd, name, held_fd):
    linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    held = os.fstat(held_fd)
    if (linked.st_dev, linked.st_ino) != (held.st_dev, held.st_ino):
        raise RuntimeError("Dedicated synthetic credential state path changed")


def verify_directory(fd):
    info = os.fstat(fd)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 10003
            or info.st_gid != 10003 or stat.S_IMODE(info.st_mode) != 0o700):
        raise RuntimeError("Dedicated synthetic credential state rejected")


def verify_marker(state_fd):
    fd = os.open(MARKER, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=state_fd)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 10003
                or info.st_gid != 10003 or stat.S_IMODE(info.st_mode) != 0o400
                or info.st_nlink != 1 or info.st_size != len(CONTENT)):
            raise RuntimeError("Dedicated synthetic credential marker rejected")
        if os.read(fd, len(CONTENT) + 1) != CONTENT:
            raise RuntimeError("Dedicated synthetic credential marker rejected")
        verify_binding(state_fd, MARKER, fd)
    finally:
        os.close(fd)


def prepare_state(parent_fd):
    created = False
    try:
        os.mkdir(STATE.name, mode=0o700, dir_fd=parent_fd)
        created = True
    except FileExistsError:
        pass
    state_fd = os.open(STATE.name, DIRECTORY_FLAGS, dir_fd=parent_fd)
    try:
        if created:
            info = os.fstat(state_fd)
            if info.st_uid != 0 or info.st_gid != os.getegid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise RuntimeError("New synthetic credential state rejected")
            # The root-only directory stays inaccessible until its immutable
            # synthetic marker is complete. Held FDs prevent path substitution.
            marker_fd = os.open(MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                0o400, dir_fd=state_fd)
            try:
                if os.write(marker_fd, CONTENT) != len(CONTENT):
                    raise RuntimeError("Synthetic credential marker write rejected")
                os.fchmod(marker_fd, 0o400)
                os.fchown(marker_fd, 10003, 10003)
                os.fsync(marker_fd)
                verify_binding(state_fd, MARKER, marker_fd)
            finally:
                os.close(marker_fd)
            verify_binding(parent_fd, STATE.name, state_fd)
            os.fchown(state_fd, 10003, 10003)
        verify_directory(state_fd)
        verify_marker(state_fd)
        verify_binding(parent_fd, STATE.name, state_fd)
    finally:
        os.close(state_fd)


def main():
    if os.geteuid() != 0:
        raise RuntimeError("Fixed synthetic credential state preparation requires root")
    parent_fd = os.open(STATE.parent, DIRECTORY_FLAGS)
    try:
        prepare_state(parent_fd)
    finally:
        os.close(parent_fd)
    print("Dedicated synthetic credential-service state verified")


if __name__ == "__main__":
    main()
