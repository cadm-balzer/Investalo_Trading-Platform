#!/usr/bin/env python3
"""Prepare only the fixed isolated synthetic check mount, never app state."""
import os
from pathlib import Path
import re
import stat
import secrets

STATE = Path("/tmp/investalo-passkey-browser-state")
MARKER = ".investalo-passkey-browser-checks"
CONTENT = b"synthetic-fixture-state-v1\n"


DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def verify_directory(fd, uid):
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or info.st_gid != 10010 or stat.S_IMODE(info.st_mode) != 0o2770:
        raise RuntimeError("Dedicated check directory ownership or mode rejected")


def verify_binding(parent_fd, name, fd):
    linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    held = os.fstat(fd)
    if (linked.st_dev, linked.st_ino) != (held.st_dev, held.st_ino):
        raise RuntimeError("Dedicated check path changed during preparation")


def prepare_file(state_fd, name, mode, data, may_create):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=state_fd)
    except FileNotFoundError:
        if not may_create:
            raise RuntimeError("Dedicated check marker missing") from None
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=state_fd)
        with os.fdopen(fd, "w") as output:
            output.write(data.decode("ascii"))
            output.flush()
            os.fchmod(output.fileno(), mode)
            os.fchown(output.fileno(), 10003, 10010)
            os.fsync(output.fileno())
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=state_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 10003 or info.st_gid != 10010 or stat.S_IMODE(info.st_mode) != mode or info.st_nlink != 1 or info.st_size != len(data):
            raise RuntimeError("Dedicated check key file rejected")
        actual = os.read(fd, len(data) + 1)
        if name == MARKER:
            valid = actual == CONTENT
        else:
            valid = re.fullmatch(rb"[0-9a-f]{64}\n", actual) is not None
        if not valid:
            raise RuntimeError("Dedicated check file contents rejected")
        verify_binding(state_fd, name, fd)
    finally:
        os.close(fd)


def prepare_state(parent_fd):
    new_state = False
    try:
        os.mkdir(STATE.name, mode=0o700, dir_fd=parent_fd)
        new_state = True
    except FileExistsError:
        pass
    state_fd = os.open(STATE.name, DIRECTORY_FLAGS, dir_fd=parent_fd)
    try:
        if new_state:
            # Keep the parent root-only until all descendants are prepared.
            info = os.fstat(state_fd)
            if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
                raise RuntimeError("New check directory rejected")
            os.mkdir("sessions", mode=0o700, dir_fd=state_fd)
        else:
            verify_directory(state_fd, 10002)
        sessions_fd = os.open("sessions", DIRECTORY_FLAGS, dir_fd=state_fd)
        try:
            if new_state:
                os.fchown(sessions_fd, 10003, 10010)
                os.fchmod(sessions_fd, 0o2770)
            verify_directory(sessions_fd, 10003)
            prepare_file(state_fd, MARKER, 0o400, CONTENT, new_state)
            # These keys cannot mint sessions or BFF assertions for the preview.
            for name in ["session-secret", "internal-secret", "oidc-secret"]:
                prepare_file(state_fd, name, 0o440, (secrets.token_hex(32) + "\n").encode("ascii"), True)
            if new_state:
                os.fchmod(state_fd, 0o2770)
                os.fchown(state_fd, 10002, 10010)
            verify_directory(state_fd, 10002)
            verify_binding(state_fd, "sessions", sessions_fd)
            verify_binding(parent_fd, STATE.name, state_fd)
        finally:
            os.close(sessions_fd)
    finally:
        os.close(state_fd)


def main():
    if os.geteuid() != 0:
        raise RuntimeError("Fixed check mount preparation requires root")
    parent_fd = os.open(STATE.parent, DIRECTORY_FLAGS)
    try:
        prepare_state(parent_fd)
    finally:
        os.close(parent_fd)
    print("Dedicated synthetic browser-check mount verified")


if __name__ == "__main__":
    main()
