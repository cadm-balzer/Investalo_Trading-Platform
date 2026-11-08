"""Privileged fixture preparation must never follow replaceable paths."""
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
    "passkey_browser_preparation", ROOT / "infra/scripts/prepare-passkey-browser-checks.py"
)
preparation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparation)


@unittest.skipUnless(os.geteuid() == 0, "Fixture UID/GID verification requires root")
class PasskeyBrowserPreparationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.parent = Path(self.folder.name)
        self.state = self.parent / "state"
        override = patch.object(preparation, "STATE", self.state)
        override.start()
        self.addCleanup(override.stop)

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            preparation.main()

    def test_fresh_and_existing_preserve_three_synthetic_keys(self):
        self.prepare()
        keys = {name: (self.state / name).read_bytes() for name in (
            "session-secret", "internal-secret", "oidc-secret"
        )}
        self.prepare()
        for name, value in keys.items():
            self.assertEqual((self.state / name).read_bytes(), value)
        self.assertEqual(len(set(keys.values())), 3)
        self.assertEqual((self.state / preparation.MARKER).read_bytes(), preparation.CONTENT)

    def test_state_symlink_cannot_change_target(self):
        target = self.parent / "target"
        target.mkdir(mode=0o700)
        self.state.symlink_to(target, target_is_directory=True)
        with self.assertRaises(OSError):
            self.prepare()
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(target.stat().st_mode & 0o7777, 0o700)

    def test_sessions_symlink_cannot_change_target(self):
        self.prepare()
        original = self.state / "sessions"
        original.rename(self.state / "old-sessions")
        target = self.parent / "target"
        target.mkdir(mode=0o700)
        original.symlink_to(target, target_is_directory=True)
        with self.assertRaises(OSError):
            self.prepare()
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(target.stat().st_mode & 0o7777, 0o700)

    def test_marker_symlink_is_rejected_before_reading(self):
        self.prepare()
        marker = self.state / preparation.MARKER
        marker.rename(self.state / "old-marker")
        marker.symlink_to(self.state / "old-marker")
        with self.assertRaises(OSError):
            self.prepare()

    def test_key_symlink_is_rejected_without_overwrite(self):
        self.prepare()
        key = self.state / "session-secret"
        original = key.read_bytes()
        key.rename(self.state / "old-key")
        key.symlink_to(self.state / "old-key")
        with self.assertRaises(OSError):
            self.prepare()
        self.assertEqual((self.state / "old-key").read_bytes(), original)

    def test_hardlinked_key_is_rejected(self):
        self.prepare()
        os.link(self.state / "session-secret", self.state / "other-key")
        with self.assertRaises(RuntimeError):
            self.prepare()

    def test_existing_mode_drift_is_rejected_without_repair(self):
        self.prepare()
        self.state.chmod(0o777)
        with self.assertRaises(RuntimeError):
            self.prepare()
        self.assertEqual(self.state.stat().st_mode & 0o7777, 0o777)

    def test_replaced_parent_does_not_redirect_privileged_changes(self):
        target = self.parent / "foreign"
        target.mkdir(mode=0o700)
        before = target.stat()
        mkdir = os.mkdir

        def replace_after_descendant_creation(name, *args, **kwargs):
            result = mkdir(name, *args, **kwargs)
            if name == "sessions":
                self.state.rename(self.parent / "held-state")
                self.state.symlink_to(target, target_is_directory=True)
            return result

        with patch.object(preparation.os, "mkdir", side_effect=replace_after_descendant_creation):
            with self.assertRaises(RuntimeError):
                self.prepare()
        after = target.stat()
        self.assertEqual((after.st_uid, after.st_gid, after.st_mode),
                         (before.st_uid, before.st_gid, before.st_mode))
        self.assertEqual(list(target.iterdir()), [])
        self.assertTrue((self.parent / "held-state" / preparation.MARKER).is_file())


if __name__ == "__main__":
    unittest.main()
