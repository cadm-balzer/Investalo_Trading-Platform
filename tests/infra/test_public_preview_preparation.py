"""Reject configuration drift and unsafe secret-file paths before preview rendering."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "public_preview_preparation", ROOT / "infra/scripts/prepare-public-preview.py"
)
preparation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparation)
SIGNING = "          -----BEGIN PRIVATE KEY-----\n          QUJDREVGRw==\n          -----END PRIVATE KEY-----"
CLIENT = '"$argon2id$v=19$m=65536,t=3,p=2$U1lOVEhFVElD$U1lOVEhFVElD"'


class PublicPreviewPreparationTests(unittest.TestCase):
    def test_public_origins_change_without_changing_existing_synthetic_secrets(self):
        template = (ROOT / "infra/authelia/configuration.template.yml").read_text()
        source = template.replace("@OIDC_SIGNING_KEY@", SIGNING).replace("@OIDC_CLIENT_HASH@", CLIENT)
        result = preparation.render(template, source)
        self.assertIn(SIGNING, result)
        self.assertIn(CLIENT, result)
        self.assertIn("'https://cockpit.investalo.de/api/auth/callback'", result)
        self.assertIn("domain: 'auth.cockpit.investalo.de'", result)
        self.assertNotIn("local.test", result)
        self.assertIn("authorization_policy: 'two_factor'", result)
        self.assertIn("require_second_factor: true", result)

    def test_drift_is_rejected_instead_of_silently_migrating_real_configuration(self):
        template = (ROOT / "infra/authelia/configuration.template.yml").read_text()
        source = template.replace("@OIDC_SIGNING_KEY@", SIGNING).replace(
            "@OIDC_CLIENT_HASH@", CLIENT
        )
        for changed in (
            source.replace("two_factor", "one_factor"),
            source.replace("filesystem:", "smtp:"),
            source.replace("require_second_factor: true", "require_second_factor: false"),
            source + "\n# unexpected operator change\n",
            source.replace(SIGNING, SIGNING + "\n    enable_client_debug_messages: true"),
            source.replace(SIGNING, SIGNING.replace("          QUJD", "    QUJD")),
            source.replace(CLIENT, '"unexpected replacement"'),
        ):
            with self.subTest(changed=changed[:40]):
                with self.assertRaises(RuntimeError) as rejected:
                    preparation.render(template, changed)
                self.assertNotIn("SYNTHETIC", str(rejected.exception))

    def test_symlink_does_not_read_its_secret_target(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target"
            target.write_text("SYNTHETIC-SECRET")
            target.chmod(0o400)
            link = Path(folder) / "link"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                preparation.read_owned(link, os.getuid(), 0o400)

    def test_hardlinked_secret_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target"
            target.write_text("SYNTHETIC-SECRET")
            target.chmod(0o400)
            os.link(target, Path(folder) / "other")
            with self.assertRaises(RuntimeError):
                preparation.read_owned(target, os.getuid(), 0o400)

    def test_permissions_and_size_must_match_before_reading(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "secret"
            path.write_text("SYNTHETIC-SECRET")
            path.chmod(0o600)
            with self.assertRaises(RuntimeError):
                preparation.read_owned(path, os.getuid(), 0o400)
            path.chmod(0o400)
            with self.assertRaises(RuntimeError):
                preparation.read_owned(path, os.getuid(), 0o400, maximum=4)
            self.assertEqual(preparation.read_owned(path, os.getuid(), 0o400), "SYNTHETIC-SECRET")

    def test_existing_foreign_preview_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "preview"
            path.write_text("OLD-SYNTHETIC-SECRET")
            path.chmod(0o600)
            with self.assertRaises(RuntimeError):
                preparation.create_config(path, "NEW-SYNTHETIC-SECRET")
            self.assertEqual(path.read_text(), "OLD-SYNTHETIC-SECRET")


if __name__ == "__main__":
    unittest.main()
