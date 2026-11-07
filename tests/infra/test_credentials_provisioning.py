"""Guard fixed fixture identities and suppress sensitive provisioning failures."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "infra/scripts/provision-local-credentials-tests.py"
SPEC = importlib.util.spec_from_file_location("credentials_provisioning", SCRIPT)
provisioning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provisioning)


class CredentialsProvisioningTests(unittest.TestCase):
    def test_arbitrary_identity_or_password_never_reaches_database(self):
        valid = {role: "S" * 64 for role in provisioning.ROLES}
        role = next(iter(valid))
        for invalid in (
            {}, {**valid, "investalo_migration": "S" * 64},
            {**valid, role: "'; ALTER ROLE investalo_admin"},
            {**valid, role: "S" * 64 + "\n"},
            {**valid, role: None},
        ):
            with patch.object(provisioning.subprocess, "run") as run:
                with self.assertRaises(RuntimeError):
                    provisioning.prepare_roles(invalid)
                run.assert_not_called()

    def test_password_is_stdin_only_and_failed_sql_is_never_exposed(self):
        password = "S" * 64
        failure = SimpleNamespace(returncode=1, stdout=password, stderr="private SQL " + password)
        with patch.object(provisioning.subprocess, "run", return_value=failure) as run:
            with self.assertRaises(RuntimeError) as rejected:
                provisioning.prepare_roles({role: password for role in provisioning.ROLES})
        args, options = run.call_args.args[0], run.call_args.kwargs
        self.assertNotIn(password, repr(args))
        self.assertIn(password, options["input"])
        self.assertTrue(options["capture_output"])
        self.assertNotIn(password, str(rejected.exception))
        self.assertNotIn("private SQL", str(rejected.exception))

    def test_existing_foreign_database_owner_is_never_changed(self):
        with patch.object(provisioning, "sql", return_value="foreign_owner") as sql:
            with self.assertRaises(RuntimeError):
                provisioning.prepare_database()
        sql.assert_called_once()

    def test_success_returns_no_sql_or_secret_output(self):
        success = SimpleNamespace(returncode=0, stdout="BEGIN\nDO\nCOMMIT\n", stderr="")
        with patch.object(provisioning.subprocess, "run", return_value=success), \
             patch("builtins.print") as emit:
            self.assertIsNone(provisioning.prepare_roles(
                {role: "S" * 64 for role in provisioning.ROLES},
            ))
        emit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
