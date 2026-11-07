"""Synthetic KEK bytes in disposable test fixtures, never existing key files."""
import dataclasses
import hashlib
import os
import pickle
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_credentials import AADBinding, SecretPayload, seal, open_envelope
from investalo_credential_store.keyfiles import (
    DevelopmentKeyFileProvider, KeyFile, KeyFileErrorCode, KeyFilesRejected,
)

KEY_1, KEY_2 = bytes(range(32)), bytes(range(32, 64))


class KeyFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-keyfile-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.directory.chmod(0o700)
        self.key = self.directory / "fixture-kek-1"
        self.key.write_bytes(KEY_1)
        self.key.chmod(0o400)
        self.spec = KeyFile("kek-1", self.key.name, hashlib.sha256(KEY_1).hexdigest())

    def provider(self, **overrides):
        return DevelopmentKeyFileProvider(**{
            "directory": str(self.directory), "files": (self.spec,),
            "active_version": "kek-1", "development_mode": True,
            "owner_uid": os.getuid(), **overrides})

    def rejected(self, code, action):
        with self.assertRaises(KeyFilesRejected) as caught:
            action()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code.value)
        self.assertIsNone(caught.exception.__cause__)
        for private in (str(self.directory), self.key.name, KEY_1.hex(), self.spec.sha256_fingerprint):
            self.assertNotIn(private, repr(caught.exception))
        return caught.exception

    def test_real_fd_loading_fingerprint_and_restart_stability(self):
        loaded = self.provider().load()
        binding = AADBinding(tenant_id=UUID(int=1), user_id=UUID(int=2), platform_account_id=UUID(int=3),
                             connection_id=UUID(int=4), broker_uid="123456", parent_uid="0",
                             credential_revision=1)
        encrypted = seal(SecretPayload(b"synthetic-payload"), binding, loaded)
        restarted = self.provider().load()
        self.assertEqual(open_envelope(encrypted, binding, restarted).reveal(), b"synthetic-payload")
        self.key.chmod(0o600)
        self.key.write_bytes(KEY_2)
        self.key.chmod(0o400)
        self.rejected(KeyFileErrorCode.FINGERPRINT_MISMATCH, lambda: self.provider().load())

    def test_active_rotation_reads_two_unique_materials(self):
        second = self.directory / "fixture-kek-2"
        second.write_bytes(KEY_2)
        second.chmod(0o400)
        spec = KeyFile("kek-2", second.name, hashlib.sha256(KEY_2).hexdigest())
        self.assertEqual(self.provider(files=(self.spec, spec), active_version="kek-2").load().active_version,
                         "kek-2")

    def test_development_marker_must_be_explicit_true_before_open(self):
        for marker in (False, None, "true", 1):
            with patch("investalo_credential_store.keyfiles.os.open") as opened:
                self.rejected(KeyFileErrorCode.DEVELOPMENT_REQUIRED,
                              lambda: self.provider(development_mode=marker))
                opened.assert_not_called()

    def test_runtime_uid_defaults_to_real_getuid_and_wrong_owner_fails(self):
        self.assertEqual(self.provider(owner_uid=None).load().active_version, "kek-1")
        self.rejected(KeyFileErrorCode.FILE_REJECTED,
                      lambda: self.provider(owner_uid=os.getuid() + 1).load())
        for owner in (-1, True, "0", 2**32):
            self.rejected(KeyFileErrorCode.INVALID_CONFIG, lambda: self.provider(owner_uid=owner))

    def test_file_owner_gate_separately_from_directory_owner(self):
        real_stat = os.fstat
        def wrong_file_owner(descriptor):
            metadata = real_stat(descriptor)
            if stat.S_ISREG(metadata.st_mode):
                fields = list(metadata)
                fields[4] = os.getuid() + 1
                return os.stat_result(fields)
            return metadata
        with patch("investalo_credential_store.keyfiles.os.fstat", side_effect=wrong_file_owner), \
             patch("investalo_credential_store.keyfiles.os.read") as read:
            self.rejected(KeyFileErrorCode.FILE_REJECTED, lambda: self.provider().load())
            read.assert_not_called()

    def test_directory_permissions_and_final_symlink_rejected(self):
        for mode in (0o750, 0o770, 0o777, 0o1700):
            self.directory.chmod(mode)
            self.rejected(KeyFileErrorCode.FILE_REJECTED, lambda: self.provider().load())
        self.directory.chmod(0o700)
        link = self.directory / "directory-link"
        link.symlink_to(self.directory, target_is_directory=True)
        self.rejected(KeyFileErrorCode.UNAVAILABLE,
                      lambda: self.provider(directory=str(link)).load())
        self.rejected(KeyFileErrorCode.UNAVAILABLE,
                      lambda: self.provider(directory=str(self.key)).load())

    def test_key_file_permissions_exact_regular_size_nlink(self):
        for mode in (0o600, 0o440, 0o404, 0o000, 0o1400):
            self.key.chmod(mode)
            self.rejected(KeyFileErrorCode.FILE_REJECTED, lambda: self.provider().load())
        self.key.chmod(0o600)
        for material in (b"", b"x" * 31, b"x" * 33, b"x" * 4096):
            self.key.write_bytes(material)
            self.key.chmod(0o400)
            self.rejected(KeyFileErrorCode.FILE_REJECTED, lambda: self.provider().load())
            self.key.chmod(0o600)
        self.key.write_bytes(KEY_1)
        self.key.chmod(0o400)
        hardlink = self.directory / "hardlink"
        os.link(self.key, hardlink)
        self.rejected(KeyFileErrorCode.FILE_REJECTED, lambda: self.provider().load())

    def test_file_symlink_directory_and_fifo_rejected_without_blocking(self):
        link = self.directory / "file-link"
        link.symlink_to(self.key)
        spec = KeyFile("kek-1", link.name, self.spec.sha256_fingerprint)
        self.rejected(KeyFileErrorCode.UNAVAILABLE, lambda: self.provider(files=(spec,)).load())
        subdir = self.directory / "not-a-file"
        subdir.mkdir(mode=0o400)
        spec = KeyFile("kek-1", subdir.name, self.spec.sha256_fingerprint)
        self.rejected(KeyFileErrorCode.FILE_REJECTED, lambda: self.provider(files=(spec,)).load())
        fifo = self.directory / "fifo"
        os.mkfifo(fifo, mode=0o400)
        spec = KeyFile("kek-1", fifo.name, self.spec.sha256_fingerprint)
        self.rejected(KeyFileErrorCode.FILE_REJECTED, lambda: self.provider(files=(spec,)).load())

    def test_fixed_basenames_ids_fingerprints_and_config_limits(self):
        for name in ("", ".", "..", "../key", "/key", "key/file", "clé", "key\n", "x" * 64):
            self.rejected(KeyFileErrorCode.INVALID_CONFIG,
                          lambda: KeyFile("kek-1", name, self.spec.sha256_fingerprint))
        for version in ("", "bad/id", "a" * 65, "kek١"):
            self.rejected(KeyFileErrorCode.INVALID_CONFIG,
                          lambda: KeyFile(version, self.key.name, self.spec.sha256_fingerprint))
        for fingerprint in ("0" * 63, "g" * 64, "A" * 64, b"x" * 32, True):
            self.rejected(KeyFileErrorCode.INVALID_CONFIG,
                          lambda: KeyFile("kek-1", self.key.name, fingerprint))
        for files in ((), [], (self.spec, self.spec),
                      tuple(KeyFile(f"k-{i}", f"file-{i}", self.spec.sha256_fingerprint)
                            for i in range(33))):
            self.rejected(KeyFileErrorCode.INVALID_CONFIG, lambda: self.provider(files=files))
        alias = KeyFile("alias", self.key.name, self.spec.sha256_fingerprint)
        self.rejected(KeyFileErrorCode.INVALID_CONFIG, lambda: self.provider(files=(self.spec, alias)))
        self.rejected(KeyFileErrorCode.INVALID_CONFIG, lambda: self.provider(active_version="missing"))
        for path in ("relative/path", "", "/bad\x00path", "x" * 4097):
            self.rejected(KeyFileErrorCode.INVALID_CONFIG, lambda: self.provider(directory=path))

    def test_material_aliases_rejected_even_with_valid_file_fingerprints(self):
        alias = self.directory / "alias"
        alias.write_bytes(KEY_1)
        alias.chmod(0o400)
        spec = KeyFile("alias", alias.name, self.spec.sha256_fingerprint)
        self.rejected(KeyFileErrorCode.INVALID_CONFIG,
                      lambda: self.provider(files=(self.spec, spec), active_version="alias").load())

    def test_no_incidental_path_material_fingerprint_serialization(self):
        for value in (self.spec, self.provider(), self.provider().load()):
            printed = repr(value) + str(value)
            for private in (str(self.directory), self.key.name, KEY_1.hex(), self.spec.sha256_fingerprint):
                self.assertNotIn(private, printed)
            for operation in (pickle.dumps, dataclasses.asdict):
                with self.assertRaises(TypeError):
                    operation(value)
            self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises(AttributeError):
            self.spec.sha256_fingerprint = "0" * 64

    def test_fd_flags_directory_relative_file_nonblocking_bounded_read_and_closure(self):
        real_open, real_read, real_close = os.open, os.read, os.close
        opened, requests, closed = [], [], []
        def tracked_open(path, flags, **options):
            result = real_open(path, flags, **options)
            opened.append((path, flags, options, result))
            return result
        def tracked_read(fd, size):
            requests.append(size)
            # Deliberately partial read verifies bounded loop, not one-shot.
            return real_read(fd, min(size, 7))
        def tracked_close(fd):
            closed.append(fd)
            return real_close(fd)
        with patch("investalo_credential_store.keyfiles.os.open", side_effect=tracked_open), \
             patch("investalo_credential_store.keyfiles.os.read", side_effect=tracked_read), \
             patch("investalo_credential_store.keyfiles.os.close", side_effect=tracked_close):
            self.provider().load()
        self.assertEqual(opened[0][1] & (os.O_NOFOLLOW | os.O_DIRECTORY), os.O_NOFOLLOW | os.O_DIRECTORY)
        self.assertEqual(opened[1][1] & (os.O_NOFOLLOW | os.O_NONBLOCK), os.O_NOFOLLOW | os.O_NONBLOCK)
        self.assertEqual(opened[1][0], self.key.name)
        self.assertEqual(opened[1][2]["dir_fd"], opened[0][3])
        self.assertTrue(all(1 <= size <= 33 for size in requests))
        self.assertEqual(set(closed), {entry[3] for entry in opened})

    def test_failing_read_static_errors_still_close_both_fds(self):
        real_close = os.close
        closed = []
        def tracked_close(fd):
            closed.append(fd)
            return real_close(fd)
        with patch("investalo_credential_store.keyfiles.os.read",
                   side_effect=OSError("synthetic raw private path/key error")), \
             patch("investalo_credential_store.keyfiles.os.close", side_effect=tracked_close):
            error = self.rejected(KeyFileErrorCode.UNAVAILABLE, lambda: self.provider().load())
        self.assertTrue(error.__suppress_context__)
        self.assertEqual(len(closed), 2)
        self.assertNotIn("private path/key", str(error))


if __name__ == "__main__":
    unittest.main()
