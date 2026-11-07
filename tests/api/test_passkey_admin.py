"""Synthetic operator tests: safe output, DB hash-only, static failure receipts."""
from contextlib import contextmanager
import hashlib
import json
import os
import stat
from uuid import uuid4

import psycopg
import pytest

import investalo_api.passkey_admin as admin
from investalo_api.passkeys import decode_b64url
from investalo_api.settings import Settings


@pytest.fixture
def args(tmp_path):
    return {
        "tenant_id": uuid4(), "user_id": uuid4(), "rp_id": "cockpit.local.test",
        "auth_epoch": 3, "confirmation_reference": uuid4(), "email_confirmed": True,
        "output_file": tmp_path / "new-ticket.json",
    }


def install_operator(monkeypatch, *, row=None, flags=None, failure=None):
    events = []
    role = {
        "login": "investalo_migration", "current": "investalo_migration",
        "rolsuper": False, "rolbypassrls": False, "rolcreaterole": False,
        "rolcreatedb": False, "rolreplication": False, **(flags or {}),
    }
    class DB:
        result = None
        def execute(self, query, values=None):
            events.append(("sql", query, values))
            if "pg_catalog.pg_roles" in query:
                self.result = role
            elif failure:
                raise failure
            else:
                self.result = row or {"ticket_id": uuid4()}
            return self
        def fetchone(self):
            return self.result
    @contextmanager
    def fake_connect(_settings):
        try:
            yield DB()
        except Exception:
            events.append("rollback")
            raise
        else:
            events.append("commit")
    monkeypatch.setattr(admin, "connect", fake_connect)
    return events


def test_issue_uses_hash_only_database_and_new_0600_file_without_printing_token(monkeypatch, args, capsys):
    events = install_operator(monkeypatch)
    ticket = admin.issue(Settings(), **args)
    content = json.loads(args["output_file"].read_text())
    token = decode_b64url(content["token"], 32, 32)
    assert stat.S_IMODE(args["output_file"].stat().st_mode) == 0o600
    assert content["ticket_id"] == str(ticket)
    issue_call = next(event for event in events if isinstance(event, tuple) and "passkey_issue_enrollment" in event[1])
    values = issue_call[2]
    assert values[3] == hashlib.sha256(token).digest()
    assert len(values[4]) == 32 and values[4] != token
    assert token not in values and content["token"] not in repr(values)
    assert events[-1] == "commit"
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("kind", ["existing", "symlink", "unsafe_directory"])
def test_issue_refuses_overwrite_symlink_or_writable_parent_before_db(monkeypatch, args, tmp_path, kind):
    events = install_operator(monkeypatch)
    if kind == "existing":
        args["output_file"].write_text("unchanged-marker")
    elif kind == "symlink":
        target = tmp_path / "target"
        target.write_text("unchanged-marker")
        args["output_file"].symlink_to(target)
    else:
        unsafe = tmp_path / "unsafe"
        unsafe.mkdir(mode=0o777)
        os.chmod(unsafe, 0o777)
        args["output_file"] = unsafe / "ticket"
    with pytest.raises((OSError, ValueError)):
        admin.issue(Settings(), **args)
    assert events == []
    if kind in ("existing", "symlink"):
        assert args["output_file"].read_text() == "unchanged-marker"


@pytest.mark.parametrize("patch", [
    {"email_confirmed": False}, {"email_confirmed": 1}, {"confirmation_reference": "not-a-uuid"},
    {"auth_epoch": True}, {"auth_epoch": -1}, {"auth_epoch": 9_007_199_254_740_992},
    {"ttl_seconds": 0}, {"ttl_seconds": 601}, {"ttl_seconds": True},
    {"user_id": "caller-subject"}, {"rp_id": "https://attacker.invalid"},
])
def test_issue_requires_explicit_operator_approval_and_bounded_identity(monkeypatch, args, patch):
    events = install_operator(monkeypatch)
    with pytest.raises(ValueError):
        admin.issue(Settings(), **{**args, **patch})
    assert events == [] and not args["output_file"].exists()


@pytest.mark.parametrize("flags", [
    {"login": "investalo_runtime"}, {"current": "investalo_runtime"},
    {"rolsuper": True}, {"rolbypassrls": True}, {"rolcreaterole": True},
    {"rolcreatedb": True}, {"rolreplication": True},
])
def test_issue_does_not_mint_ticket_under_wrong_or_drifted_login(monkeypatch, args, flags):
    events = install_operator(monkeypatch, flags=flags)
    with pytest.raises(ValueError, match="migration identity"):
        admin.issue(Settings(), **args)
    assert events[-1] == "rollback"
    assert not any(isinstance(event, tuple) and "passkey_issue_enrollment" in event[1] for event in events)
    assert args["output_file"].read_bytes() == b""


def test_output_write_failure_rolls_back_ticket_and_never_emits_secret(monkeypatch, args, capsys):
    events = install_operator(monkeypatch)
    def fail_flush(_fd):
        raise OSError("private-path-marker")
    monkeypatch.setattr(admin.os, "fsync", fail_flush)
    with pytest.raises(ValueError, match="reconcile"):
        admin.issue(Settings(), **args)
    assert events[-1] == "rollback" and "commit" not in events
    assert capsys.readouterr().out == ""


def test_unknown_commit_keeps_protected_artifact_for_operator_reconciliation(monkeypatch, args):
    @contextmanager
    def fail_commit(settings):
        class DB:
            result = None
            def execute(self, query, values=None):
                self.result = {
                    "login": "investalo_migration", "current": "investalo_migration",
                    "rolsuper": False, "rolbypassrls": False, "rolcreaterole": False,
                    "rolcreatedb": False, "rolreplication": False,
                } if "pg_roles" in query else {"ticket_id": uuid4()}
                return self
            def fetchone(self):
                return self.result
        yield DB()
        raise psycopg.OperationalError("private-connection-marker")
    monkeypatch.setattr(admin, "connect", fail_commit)
    with pytest.raises(ValueError, match="reconcile"):
        admin.issue(Settings(), **args)
    assert len(decode_b64url(json.loads(args["output_file"].read_text())["token"], 32, 32)) == 32
    assert stat.S_IMODE(args["output_file"].stat().st_mode) == 0o600


def test_revoke_requires_cas_and_approval_then_returns_only_receipt(monkeypatch, args):
    key = uuid4()
    row = {
        "passkey_id": key, "tenant_id": args["tenant_id"], "user_id": args["user_id"],
        "rp_id": args["rp_id"], "credential_id": b"fixture-id", "user_handle": b"h" * 32,
        "public_key": b"fixture-public", "sign_count": 0, "backup_eligible": True,
        "backed_up": False, "storage_version": 3, "status": "revoked", "enrollment_epoch": 3,
    }
    events = install_operator(monkeypatch, row=row)
    result = admin.revoke(
        Settings(), passkey_id=key, expected_storage=2,
        confirmation_reference=args["confirmation_reference"], email_confirmed=True,
    )
    assert result == {"passkey_id": str(key), "storage_version": 3, "status": "revoked"}
    assert events[-1] == "commit"
    call = next(event for event in events if isinstance(event, tuple) and "passkey_admin_revoke" in event[1])
    assert call[2] == (key, 2, args["confirmation_reference"])
    with pytest.raises(ValueError):
        admin.revoke(Settings(), passkey_id=key, expected_storage=True,
                     confirmation_reference=args["confirmation_reference"], email_confirmed=True)
    with pytest.raises(ValueError):
        admin.revoke(Settings(), passkey_id=key, expected_storage=2,
                     confirmation_reference=args["confirmation_reference"], email_confirmed=False)


def test_cli_reports_no_token_no_input_and_no_false_email_delivery(monkeypatch, args, capsys):
    install_operator(monkeypatch)
    monkeypatch.setattr(admin.Settings, "from_environment", classmethod(lambda cls: Settings()))
    command = [
        "issue", "--tenant-id", str(args["tenant_id"]), "--user-id", str(args["user_id"]),
        "--rp-id", args["rp_id"], "--auth-epoch", "3", "--email-confirmed",
        "--confirmation-reference", str(args["confirmation_reference"]),
        "--output-file", str(args["output_file"]),
    ]
    assert admin.main(command) == 0
    captured = capsys.readouterr()
    token = json.loads(args["output_file"].read_text())["token"]
    assert token not in captured.out + captured.err and str(args["output_file"]) not in captured.out
    assert "no email sent" in captured.out
    assert admin.main(command) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "Passkey operation unavailable; inspect protected state before retry.\n"
    assert token not in captured.err
