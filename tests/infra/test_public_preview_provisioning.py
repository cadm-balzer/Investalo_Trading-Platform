"""Exercise preview authority and private receipt handling without DBs or secrets."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

SCRIPT = Path(__file__).resolve().parents[2] / "infra/scripts/provision-public-preview.py"
SPEC = importlib.util.spec_from_file_location("public_preview_provisioning", SCRIPT)
provisioning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provisioning)

SUBJECT = "ab000000-0000-4000-8000-000000000001"
USER = "ab000000-0000-4000-8000-000000000002"
TENANT = "ab000000-0000-4000-8000-000000000003"
SOURCE = {
    "username": "pilot", "subject": SUBJECT,
    "issuer": "https://auth.cockpit.local.test:8443",
    "tenant_name": "Lokale Entwicklung",
}
RECEIPT = {"user_id": USER, "tenant_id": TENANT}


class PublicPreviewProvisioningTests(unittest.TestCase):
    def test_non_synthetic_authority_and_noncanonical_subject_are_rejected(self):
        for value in (
            None, [], {}, {**SOURCE, "username": "real-user"},
            {**SOURCE, "issuer": provisioning.ISSUER},
            {**SOURCE, "issuer": "https://foreign.example.invalid"},
            {**SOURCE, "tenant_name": "Other tenant"},
            {**SOURCE, "role": "owner"}, {**SOURCE, "tenant_id": TENANT},
            {**SOURCE, "subject": None}, {**SOURCE, "subject": "'; private-sentinel"},
            {**SOURCE, "subject": SUBJECT.upper()},
        ):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises((RuntimeError, ValueError)):
                    provisioning.source_identity(value)
        with patch.object(provisioning.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                provisioning.provision("'; private-sentinel")
            run.assert_not_called()

    def test_operator_role_and_unambiguous_existing_tenant_precede_any_write(self):
        for role, rows in (
            ("investalo_runtime", [{"tenant_id": UUID(TENANT)}]),
            ("investalo_migration", []),
            ("investalo_migration", [{"tenant_id": UUID(TENANT)}] * 2),
        ):
            with self.subTest(role=role, rows=len(rows)):
                db = MagicMock()
                db.execute.return_value.fetchone.return_value = {"name": role}
                db.execute.return_value.fetchall.return_value = rows
                connection = MagicMock()
                connection.__enter__.return_value = db
                writer = Mock()
                database = ModuleType("investalo_api.database")
                database.connect = Mock(return_value=connection)
                provision = ModuleType("investalo_api.provision")
                provision.provision = writer
                settings = ModuleType("investalo_api.settings")
                settings.Settings = SimpleNamespace(from_environment=Mock(return_value=object()))
                with patch.dict(sys.modules, {
                    "investalo_api": ModuleType("investalo_api"),
                    "investalo_api.database": database,
                    "investalo_api.provision": provision,
                    "investalo_api.settings": settings,
                }), patch("builtins.print") as emit:
                    with self.assertRaises(RuntimeError):
                        exec(provisioning.operator_program(SUBJECT), {})
                writer.assert_not_called()
                emit.assert_not_called()

    def test_failed_subprocess_captures_private_output_without_reemitting_it(self):
        sentinel = "SYNTHETIC-PRIVATE-SENTINEL"
        failure = SimpleNamespace(returncode=1, stdout=sentinel, stderr="Operator identity required " + sentinel)
        with patch.object(provisioning.subprocess, "run", return_value=failure) as run, \
                patch("builtins.print") as emit:
            with self.assertRaises(RuntimeError) as rejected:
                provisioning.provision(SUBJECT)
        emit.assert_not_called()
        self.assertNotIn(sentinel, str(rejected.exception))
        self.assertIn("reconcile before retry", str(rejected.exception))
        args, options = run.call_args.args[0], run.call_args.kwargs
        self.assertNotIn(SUBJECT, repr(args))
        self.assertIn(SUBJECT, options["input"])
        self.assertTrue(options["capture_output"])
        self.assertNotIn("shell", options)

    def test_malformed_or_expanded_receipts_fail_without_private_output(self):
        for wire in (
            "SYNTHETIC-PRIVATE-SENTINEL", "null", "[]",
            json.dumps({**RECEIPT, "private": "SYNTHETIC-PRIVATE-SENTINEL"}),
            json.dumps({"user_id": "SYNTHETIC-PRIVATE-SENTINEL", "tenant_id": TENANT}),
            json.dumps({**RECEIPT, "user_id": True}),
            json.dumps({**RECEIPT, "user_id": USER.upper()}),
        ):
            with self.subTest(wire_type=wire[:1]):
                output = SimpleNamespace(returncode=0, stdout=wire, stderr="")
                with patch.object(provisioning.subprocess, "run", return_value=output), \
                        patch("builtins.print") as emit:
                    with self.assertRaises((RuntimeError, ValueError)) as rejected:
                        provisioning.provision(SUBJECT)
                self.assertNotIn("SYNTHETIC-PRIVATE-SENTINEL", str(rejected.exception))
                emit.assert_not_called()
        output = SimpleNamespace(returncode=0, stdout=json.dumps(RECEIPT), stderr="")
        with patch.object(provisioning.subprocess, "run", return_value=output), \
                patch("builtins.print") as emit:
            self.assertEqual(provisioning.provision(SUBJECT), RECEIPT)
        emit.assert_not_called()

    def test_foreign_manifest_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(provisioning, "LOCAL", Path(folder)):
            path = Path(folder) / "public-preview-identity.json"
            path.write_text("FOREIGN-SYNTHETIC-CONTENT")
            path.chmod(0o600)
            with self.assertRaises(RuntimeError):
                provisioning.save_manifest(RECEIPT)
            self.assertEqual(path.read_text(), "FOREIGN-SYNTHETIC-CONTENT")

    def test_symlink_and_hardlink_targets_remain_untouched(self):
        for kind in ("symlink", "hardlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder, \
                    patch.object(provisioning, "LOCAL", Path(folder)):
                target = Path(folder) / "target"
                target.write_text("FOREIGN-SYNTHETIC-CONTENT")
                target.chmod(0o600)
                path = Path(folder) / "public-preview-identity.json"
                if kind == "symlink":
                    path.symlink_to(target)
                else:
                    os.link(target, path)
                with self.assertRaises((OSError, RuntimeError)):
                    provisioning.save_manifest(RECEIPT)
                self.assertEqual(target.read_text(), "FOREIGN-SYNTHETIC-CONTENT")


if __name__ == "__main__":
    unittest.main()
