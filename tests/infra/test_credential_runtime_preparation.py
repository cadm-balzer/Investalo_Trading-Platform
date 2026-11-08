"""Root preparation never follows or repairs untrusted fixture paths."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "credential_runtime_preparation", ROOT / "infra/scripts/prepare-credential-runtime-checks.py")
preparation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparation)


@unittest.skipUnless(os.geteuid() == 0, "Fixture UID/GID verification requires root")
class CredentialRuntimePreparationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.parent = Path(folder.name)
        self.state = self.parent / "state"
        override = patch.object(preparation, "STATE", self.state)
        override.start()
        self.addCleanup(override.stop)

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            preparation.main()

    def test_create_and_verify_preserve_marker_and_existing_run(self):
        self.prepare()
        marker = self.state / preparation.MARKER
        before = marker.stat()
        (self.state / "existing-run").mkdir(mode=0o700)
        self.prepare()
        after = marker.stat()
        self.assertEqual((after.st_ino, after.st_size), (before.st_ino, before.st_size))
        self.assertEqual(marker.read_bytes(), preparation.CONTENT)
        self.assertEqual((self.state.stat().st_uid, self.state.stat().st_gid,
                          self.state.stat().st_mode & 0o7777), (10003, 10003, 0o700))
        self.assertTrue((self.state / "existing-run").is_dir())
        self.assertEqual(sorted(path.name for path in self.state.iterdir()),
                         [preparation.MARKER, "existing-run"])

    def test_state_symlink_preserves_foreign_target(self):
        target = self.parent / "foreign"
        target.mkdir(mode=0o700)
        before = target.stat()
        self.state.symlink_to(target, target_is_directory=True)
        with self.assertRaises(OSError):
            self.prepare()
        after = target.stat()
        self.assertEqual((after.st_uid, after.st_gid, after.st_mode),
                         (before.st_uid, before.st_gid, before.st_mode))
        self.assertEqual(list(target.iterdir()), [])

    def test_marker_symlink_rejected(self):
        self.prepare()
        marker = self.state / preparation.MARKER
        marker.rename(self.state / "original")
        marker.symlink_to(self.state / "original")
        with self.assertRaises(OSError):
            self.prepare()

    def test_marker_hardlink_rejected(self):
        self.prepare()
        os.link(self.state / preparation.MARKER, self.state / "copy")
        with self.assertRaises(RuntimeError):
            self.prepare()

    def test_missing_existing_marker_never_recreated(self):
        self.prepare()
        (self.state / preparation.MARKER).rename(self.state / "original")
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        self.assertFalse((self.state / preparation.MARKER).exists())

    def test_wrong_marker_content_never_repaired(self):
        self.prepare()
        marker = self.state / preparation.MARKER
        marker.chmod(0o600)
        marker.write_bytes(b"x" * len(preparation.CONTENT))
        marker.chmod(0o400)
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertEqual(marker.read_bytes(), b"x" * len(preparation.CONTENT))

    def test_wrong_marker_mode_never_repaired(self):
        self.prepare()
        (self.state / preparation.MARKER).chmod(0o440)
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertEqual((self.state / preparation.MARKER).stat().st_mode & 0o7777, 0o440)

    def test_wrong_directory_mode_never_repaired(self):
        self.prepare()
        self.state.chmod(0o770)
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertEqual(self.state.stat().st_mode & 0o7777, 0o770)

    def test_replaced_state_path_never_changes_foreign_target(self):
        target = self.parent / "foreign"
        target.mkdir(mode=0o700)
        before = target.stat()
        open_original = preparation.os.open

        def replace_after_marker_create(name, flags, *args, **kwargs):
            result = open_original(name, flags, *args, **kwargs)
            if name == preparation.MARKER and flags & os.O_CREAT:
                self.state.rename(self.parent / "held")
                self.state.symlink_to(target, target_is_directory=True)
            return result

        with patch.object(preparation.os, "open", side_effect=replace_after_marker_create):
            with self.assertRaises(RuntimeError):
                self.prepare()
        after = target.stat()
        self.assertEqual((after.st_uid, after.st_gid, after.st_mode),
                         (before.st_uid, before.st_gid, before.st_mode))
        self.assertEqual(list(target.iterdir()), [])

    def test_nonroot_rejected_before_creating_state(self):
        with patch.object(preparation.os, "geteuid", return_value=10003):
            with self.assertRaises(RuntimeError):
                self.prepare()
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
