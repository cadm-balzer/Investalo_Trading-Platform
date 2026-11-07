"""Development-only pinned KEK reader. No writer, remote provider or live keys."""
from __future__ import annotations

from enum import StrEnum
import hashlib
import hmac
import os
import re
import stat

from investalo_credentials import EnvelopeRejected, KEKRing, MAX_KEY_SLOTS
from .models import _PrivateImmutable


class KeyFileErrorCode(StrEnum):
    DEVELOPMENT_REQUIRED = "development_required"
    INVALID_CONFIG = "invalid_keyfile_config"
    FILE_REJECTED = "keyfile_rejected"
    FINGERPRINT_MISMATCH = "keyfile_fingerprint_mismatch"
    UNAVAILABLE = "keyfile_unavailable"


class KeyFilesRejected(ValueError):
    def __init__(self, code: KeyFileErrorCode):
        if not isinstance(code, KeyFileErrorCode):
            code = KeyFileErrorCode.UNAVAILABLE
        self.code = code
        super().__init__(code.value)


class KeyFile(_PrivateImmutable):
    __slots__ = ("version_id", "basename", "sha256_fingerprint")

    def __init__(self, version_id: str, basename: str, sha256_fingerprint: str):
        if (not isinstance(version_id, str) or not 1 <= len(version_id) <= 64
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", version_id)
                or not isinstance(basename, str) or not 1 <= len(basename) <= 63
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}", basename)
                or not isinstance(sha256_fingerprint, str) or len(sha256_fingerprint) != 64
                or not re.fullmatch(r"[0-9a-f]{64}", sha256_fingerprint)):
            raise KeyFilesRejected(KeyFileErrorCode.INVALID_CONFIG) from None
        object.__setattr__(self, "version_id", version_id)
        object.__setattr__(self, "basename", basename)
        object.__setattr__(self, "sha256_fingerprint", sha256_fingerprint)


def _file_stat(metadata: os.stat_result, owner_uid: int):
    if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o400
            or metadata.st_uid != owner_uid or metadata.st_nlink != 1 or metadata.st_size != 32):
        raise KeyFilesRejected(KeyFileErrorCode.FILE_REJECTED) from None


class DevelopmentKeyFileProvider(_PrivateImmutable):
    __slots__ = ("_directory", "_files", "_active_version", "_owner_uid")

    def __init__(self, directory: str, files: tuple[KeyFile, ...], *, active_version: str,
                 development_mode: bool, owner_uid: int | None = None):
        if development_mode is not True:
            raise KeyFilesRejected(KeyFileErrorCode.DEVELOPMENT_REQUIRED) from None
        if owner_uid is None:
            owner_uid = os.getuid()
        if (type(owner_uid) is not int or not 0 <= owner_uid < 2**32
                or not isinstance(directory, str) or not 1 <= len(directory) <= 4096
                or not os.path.isabs(directory) or "\0" in directory
                or not isinstance(files, tuple) or not 1 <= len(files) <= MAX_KEY_SLOTS
                or any(not isinstance(entry, KeyFile) for entry in files)):
            raise KeyFilesRejected(KeyFileErrorCode.INVALID_CONFIG) from None
        versions = tuple(entry.version_id for entry in files)
        names = tuple(entry.basename for entry in files)
        if (len(set(versions)) != len(versions) or len(set(names)) != len(names)
                or type(active_version) is not str or active_version not in versions):
            raise KeyFilesRejected(KeyFileErrorCode.INVALID_CONFIG) from None
        object.__setattr__(self, "_directory", directory)
        object.__setattr__(self, "_files", files)
        object.__setattr__(self, "_active_version", active_version)
        object.__setattr__(self, "_owner_uid", owner_uid)

    def load(self) -> KEKRing:
        """Read only fixed trusted files through pinned directory/file FDs."""
        try:
            directory = os.open(self._directory, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                metadata = os.fstat(directory)
                if (not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700
                        or metadata.st_uid != self._owner_uid):
                    raise KeyFilesRejected(KeyFileErrorCode.FILE_REJECTED) from None
                entries = []
                for entry in self._files:
                    descriptor = os.open(entry.basename,
                                         os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                                         dir_fd=directory)
                    try:
                        _file_stat(os.fstat(descriptor), self._owner_uid)
                        # Never trust st_size alone. Read at most 33 bytes so a
                        # concurrent growth or an oversized file fails closed.
                        chunks = []
                        size = 0
                        while size < 33:
                            chunk = os.read(descriptor, 33 - size)
                            if not chunk:
                                break
                            chunks.append(chunk)
                            size += len(chunk)
                        material = b"".join(chunks)
                        _file_stat(os.fstat(descriptor), self._owner_uid)
                        if len(material) != 32:
                            raise KeyFilesRejected(KeyFileErrorCode.FILE_REJECTED) from None
                        if not hmac.compare_digest(hashlib.sha256(material).hexdigest(),
                                                   entry.sha256_fingerprint):
                            raise KeyFilesRejected(KeyFileErrorCode.FINGERPRINT_MISMATCH) from None
                        entries.append((entry.version_id, material))
                    finally:
                        os.close(descriptor)
                return KEKRing(tuple(entries), active_version=self._active_version)
            finally:
                os.close(directory)
        except KeyFilesRejected:
            raise
        except EnvelopeRejected:
            raise KeyFilesRejected(KeyFileErrorCode.INVALID_CONFIG) from None
        except PermissionError:
            raise KeyFilesRejected(KeyFileErrorCode.FILE_REJECTED) from None
        except Exception:
            # Suppress OSError/UnicodeError chains containing path/config data.
            raise KeyFilesRejected(KeyFileErrorCode.UNAVAILABLE) from None
