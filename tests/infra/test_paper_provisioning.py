import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("paper_provision", ROOT/"infra/scripts/provision-paper-development.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PaperProvisioning(unittest.TestCase):
    def test_manifest_rejects_foreign_role_database_and_noncanonical_ids(self):
        value = {"schema": "paper-development/1", "database": module.DATABASE, "role": module.ROLE,
                 "tenant": str(uuid4()), "account": str(uuid4()), "state": "bound"}
        self.assertEqual(module.manifest(value), value)
        for key, change in (("role", "investalo_paper_tests"), ("database", "investalo"),
                            ("tenant", "other"), ("state", "other")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.manifest({**value, key: change})

    def test_protected_files_reject_symlinks_hardlinks_and_broad_permissions(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); path = root/"manifest"
            module.write_new(path, "safe", 0o600, os.getuid())
            self.assertEqual(module.protected(path, os.getuid(), 0o600), "safe")
            alias = root/"alias"; alias.symlink_to(path)
            with self.assertRaises(ValueError): module.protected(alias, os.getuid(), 0o600)
            os.link(path, root/"hard")
            with self.assertRaises(ValueError): module.protected(path, os.getuid(), 0o600)
            second = root/"second"
            module.write_new(second, "safe", 0o600, os.getuid())
            second.chmod(0o644)
            with self.assertRaises(ValueError): module.protected(second, os.getuid(), 0o600)

    def test_exclusive_creation_never_overwrites_existing_secret(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name)/"secret"
            module.write_new(path, "first", 0o600, os.getuid())
            with self.assertRaises(FileExistsError):
                module.write_new(path, "second", 0o600, os.getuid())
            self.assertEqual(path.read_text(), "first")


if __name__ == "__main__":
    unittest.main()
