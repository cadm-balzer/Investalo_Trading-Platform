from pathlib import Path
from uuid import uuid4

import pytest

from investalo_workers.settings import WorkerSettings


def test_worker_never_reads_browser_or_broker_credentials(monkeypatch, tmp_path):
    credential = tmp_path / "research-password"
    value = uuid4().hex + uuid4().hex
    credential.write_text(value)
    monkeypatch.setenv("PGSSLMODE", "verify-full")
    monkeypatch.setenv("PGUSER", "isolated-test-login")
    monkeypatch.setenv("PGPASSWORD_FILE", str(credential))
    monkeypatch.setenv("API_INTERNAL_AUTH_SECRET_FILE", "/must-not-read")
    monkeypatch.setenv("BFF_INTERNAL_AUTH_SECRET_FILE", "/must-not-read")
    actual_read = Path.read_text
    def guarded_read(path, *args, **kwargs):
        assert path == credential
        return actual_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    settings = WorkerSettings.from_environment()
    assert settings.parameters["password"] == value
    assert value not in repr(settings)


@pytest.mark.parametrize("mode", ["disable", "prefer", "require"])
def test_worker_refuses_unverified_database_tls(monkeypatch, mode):
    monkeypatch.setenv("PGSSLMODE", mode)
    with pytest.raises(ValueError, match="verified database TLS"):
        WorkerSettings.from_environment()
