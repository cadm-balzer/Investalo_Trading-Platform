import os
from unittest.mock import Mock

import pytest

from investalo_workers import paper_preview_once as preview
from investalo_workers.paper_store import PaperCommitUnknown

ENV = {
    "PAPER_WORKER_ENABLED": "1", "PAPER_PUBLIC_PREVIEW_MODE": "1",
    "PGHOST": "postgres", "PGPORT": "5432", "PGDATABASE": "investalo",
    "PGUSER": "investalo_paper_preview", "PGSSLMODE": "verify-full",
    "PGSSLROOTCERT": "/run/secrets/local_ca_cert",
    "PGPASSWORD_FILE": "/run/secrets/paper_preview_password",
}


def environment(monkeypatch):
    for key in list(os.environ):
        if key.startswith("PG"):
            monkeypatch.delenv(key)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)


def test_exact_preview_environment(monkeypatch):
    environment(monkeypatch)
    preview.require_preview()


@pytest.mark.parametrize("key,value", [
    ("PAPER_PUBLIC_PREVIEW_MODE", "0"), ("PGDATABASE", "investalo_credentials_checks"),
    ("PGUSER", "investalo_runtime"), ("PGUSER", "investalo_paper_development"),
    ("PGHOST", "foreign.invalid"), ("PGSSLMODE", "require"),
    ("PGPASSWORD", "unsafe"), ("PGOPTIONS", "-c role=investalo_admin"),
    ("PGSERVICE", "unsafe"),
])
def test_ambient_or_foreign_identity_rejected(monkeypatch, key, value):
    environment(monkeypatch)
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        preview.require_preview()


def test_mode_required_before_connection(monkeypatch):
    configure = Mock()
    monkeypatch.setattr(preview, "configured_worker", configure)
    monkeypatch.setattr("sys.argv", ["paper-preview"])
    with pytest.raises(SystemExit) as error:
        preview.main()
    assert error.value.code == 2
    configure.assert_not_called()


def test_unknown_commit_is_terminal_without_retry_or_sensitive_diagnostic(monkeypatch):
    environment(monkeypatch)
    worker = Mock()
    worker.run_once.side_effect = PaperCommitUnknown("sensitive detail")
    monkeypatch.setattr(preview, "configured_worker", lambda: worker)
    monkeypatch.setattr("sys.argv", ["paper-preview", "--once"])
    with pytest.raises(SystemExit, match="readback required") as error:
        preview.main()
    assert "sensitive detail" not in str(error.value)
    worker.run_once.assert_called_once()
