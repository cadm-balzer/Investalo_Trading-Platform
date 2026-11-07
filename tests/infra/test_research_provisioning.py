"""Unit guards; Root separately exercises the transaction against PostgreSQL."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / "infra/scripts/provision-local-research.py"
SPEC = importlib.util.spec_from_file_location("research_provisioning", SCRIPT)
provisioning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provisioning)


class ResearchProvisioningTests(unittest.TestCase):
    def test_untrusted_role_and_secret_never_reach_psql(self):
        cases = (
            ("investalo_migration", "A" * 64),
            ("investalo_research_local; GRANT ALL TO PUBLIC", "A" * 64),
            ("investalo_research_local", "'; ALTER ROLE investalo_admin"),
            ("investalo_research_local", "A" * 64 + "\n"),
            ("investalo_research_local", None),
        )
        with patch.object(provisioning.subprocess, "run") as run:
            for role, password in cases:
                with self.subTest(role=role), self.assertRaises(RuntimeError):
                    provisioning.prepare_roles(role, password)
            run.assert_not_called()

    def test_one_guarded_transaction_before_any_creation_or_grant(self):
        # Both fixed identities must preserve the same isolation contract.
        for role in ("investalo_research_local", "investalo_research_tests"):
            with self.subTest(role=role), patch.object(provisioning, "sql") as execute:
                provisioning.prepare_roles(role, "A" * 64)
                execute.assert_called_once()
                command = execute.call_args.args[0].strip()
                self.assertTrue(command.startswith("BEGIN;"))
                self.assertTrue(command.endswith("COMMIT;"))
                privilege_guard = command.index("Research role has unexpected privileges")
                membership_guard = command.index("Research role has unexpected memberships")
                first_creation = command.index("CREATE ROLE")
                first_grant = command.index("GRANT ")
                self.assertLess(privilege_guard, first_creation)
                self.assertLess(membership_guard, first_creation)
                self.assertLess(first_creation, first_grant)
                # The group cannot inherit another role, and the login may
                # inherit only this group without delegating its membership.
                self.assertIn("member_role.rolname='investalo_research_worker'", command)
                self.assertIn("parent_role.rolname<>'investalo_research_worker'", command)
                self.assertIn("membership.admin_option", command)
                self.assertNotIn("EXCEPTION WHEN", command)
                self.assertNotIn("ALTER ROLE", command)
                self.assertNotIn("REVOKE ", command)
                self.assertNotIn("DROP ", command)

    def test_psql_failure_is_sanitized_and_secret_is_not_in_process_arguments(self):
        password = "S" * 64
        failure = SimpleNamespace(returncode=1, stdout=password, stderr="SQL containing " + password)
        with patch.object(provisioning.subprocess, "run", return_value=failure) as run:
            with self.assertRaises(RuntimeError) as rejected:
                provisioning.prepare_roles("investalo_research_local", password)
        run.assert_called_once()
        arguments, options = run.call_args.args[0], run.call_args.kwargs
        self.assertNotIn(password, repr(arguments))
        self.assertIn(password, options["input"])
        self.assertIn("ON_ERROR_STOP=1", arguments)
        self.assertTrue(options["capture_output"])
        self.assertNotIn(password, str(rejected.exception))
        self.assertNotIn("SQL containing", str(rejected.exception))

    def test_success_does_not_emit_secret_or_return_sql_output(self):
        password = "S" * 64
        success = SimpleNamespace(returncode=0, stdout="BEGIN\nDO\nCOMMIT\n", stderr="")
        with patch.object(provisioning.subprocess, "run", return_value=success), \
             patch("builtins.print") as emit:
            self.assertIsNone(provisioning.prepare_roles("investalo_research_local", password))
        emit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
