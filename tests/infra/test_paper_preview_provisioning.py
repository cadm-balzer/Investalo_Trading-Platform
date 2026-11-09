from pathlib import Path
import runpy
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
PREVIEW = runpy.run_path(str(ROOT/"infra/scripts/provision-paper-preview.py"))


class PaperPreviewProvisioning(unittest.TestCase):
    def setUp(self):
        self.actor = {
            "username": "pilot", "issuer": PREVIEW["ISSUER"], "tenant_name": "Lokale Entwicklung",
            "subject": str(uuid4()), "user_id": str(uuid4()), "tenant_id": str(uuid4()),
        }
        self.value = {
            "schema": "paper-preview/1", "database": "investalo", "role": PREVIEW["ROLE"],
            "user_id": self.actor["user_id"], "tenant": self.actor["tenant_id"],
            "account": str(uuid4()), "state": "prepared",
        }

    def test_only_explicit_public_development_identity(self):
        PREVIEW["public_identity"](self.actor)
        for key, value in (("issuer", "https://foreign.invalid"), ("username", "other"),
                           ("subject", "not-a-uuid"), ("tenant_name", "other")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                PREVIEW["public_identity"]({**self.actor, key: value})

    def test_manifest_refuses_actor_tenant_database_and_role_drift(self):
        PREVIEW["manifest"](self.value, self.actor)
        for key, value in (("user_id", str(uuid4())), ("tenant", str(uuid4())),
                           ("database", "investalo_credentials_checks"),
                           ("role", "investalo_paper_development"), ("state", "unknown")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                PREVIEW["manifest"]({**self.value, key: value}, self.actor)


if __name__ == "__main__":
    unittest.main()
