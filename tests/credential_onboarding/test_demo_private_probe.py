"""Actual private IO/locks, guarded TTY entry and synthetic signed replies."""
import getpass
import json
import os
import pty
import select
import stat
import sys
import time
import warnings
from pathlib import Path
from uuid import UUID

import pytest
from investalo_bitget import Credentials, ReadResponse
from investalo_credential_store import demo_private_probe as own

AT = 1_700_000_000_100
TRIPLE = Credentials("synthetic-probe-api", "synthetic-probe-secret-ß", "synthetic-probe-pass")


def fields():
    return dict(schema=own.SCHEMA, tenant_id=str(UUID(int=1)), user_id=str(UUID(int=2)),
        account_id=str(UUID(int=3)), connection_id=str(UUID(int=4)), broker_uid="123456",
        parent_uid="0", egress_ip="192.0.2.18", authorities=["coor", "cpor"])


def setup(tmp_path, **changes):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    path = root / "setup.json"
    path.write_text(json.dumps({**fields(), **changes}))
    path.chmod(0o400)
    return own.PrivateProbeSetup(str(root), owner_uid=os.getuid())


def reply(request):
    assert request.axis == "identity"
    assert request.headers["paptrading"] == "1"
    return ReadResponse(200, json.dumps(dict(code="00000", requestTime=AT, data=dict(
        userId="123456", parentId=0, ips="192.0.2.18", authorities=["coor", "cpor"]))).encode())


def invoke(value, transport=reply, **changes):
    return own.probe(value, TRIPLE, **{**dict(confirmed_demo_origin=True,
                    transport=transport, milliseconds=lambda: AT), **changes})


def test_actual_private_receipt_contains_no_triple_or_mac_key(tmp_path):
    value = setup(tmp_path)
    calls = []
    def transport(request):
        calls.append(request)
        return reply(request)
    run_id = invoke(value, transport)
    root = Path(value.root)
    directory = root/run_id
    path = directory/"receipt.json"
    assert len(calls) == 1
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    raw = path.read_bytes()
    record = json.loads(raw)
    assert record["status"] == "identity_checked"
    assert record["spec"]["binding"]["account"] == fields()["account_id"]
    assert record["spec"]["binding"]["credential_ref"] == fields()["connection_id"]
    assert record["response"]["started_ms"] == record["response"]["returned_ms"] == AT
    assert record["response"]["target"] == "/api/v2/spot/account/info"
    assert len(record["response"]["response_sha256"]) == 64
    for field in ("native_demo_creation_verified", "full_account_acceptance_verified",
                  "platform_registration", "order_dispatch"):
        assert record[field] is False
    assert all(part not in raw for part in (
        TRIPLE._api_key.encode(), TRIPLE._secret_key, TRIPLE._passphrase.encode()))
    assert sorted(p.name for p in directory.iterdir()) == ["receipt.json"]
    # Original config stays fixed, future explicit operator probes get new artifacts.
    assert (root/"setup.json").read_text() == json.dumps(fields())


@pytest.mark.parametrize("changes", [dict(credentials="untrusted"), dict(confirmed_demo_origin=False),
                                       dict(confirmed_demo_origin=1)])
def test_reject_before_send_or_artifact(tmp_path, changes):
    value = setup(tmp_path)
    calls = []
    credentials = changes.pop("credentials", TRIPLE)
    with pytest.raises(own.PrivateProbeRejected):
        own.probe(value, credentials, transport=lambda r: calls.append(r),
            confirmed_demo_origin=changes.get("confirmed_demo_origin", True), milliseconds=lambda: AT)
    assert calls == []
    assert sorted(p.name for p in Path(value.root).iterdir()) == ["setup.json"]


@pytest.mark.parametrize("changes", [dict(schema="normal-probe/1"), dict(api_key="must-never-be-intake"),
    dict(parent_uid=None), dict(authorities=["coor", "cpor", "trade"]), dict(tenant_id="untrusted")])
def test_setup_is_strict_private_metadata_only(tmp_path, changes):
    with pytest.raises(own.PrivateProbeRejected):
        setup(tmp_path, **changes)


def test_actual_busy_directory_lock_rejects_second_operator_probe(tmp_path):
    value = setup(tmp_path)
    fd = os.open(value.root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        own.fcntl.flock(fd, own.fcntl.LOCK_EX | own.fcntl.LOCK_NB)
        with pytest.raises(own.PrivateProbeRejected):
            invoke(value, lambda _: pytest.fail("busy must not send"))
    finally:
        os.close(fd)
    invoke(value)


def test_setup_mutation_during_get_preserves_failed_attempt_without_retry(tmp_path):
    value = setup(tmp_path)
    calls = []
    def transport(request):
        calls.append(request)
        path = Path(value.root)/"setup.json"
        path.chmod(0o600)
        path.write_text(json.dumps({**fields(), "broker_uid": "654321"}))
        path.chmod(0o400)
        return reply(request)
    with pytest.raises(own.PrivateProbeRejected):
        invoke(value, transport)
    assert len(calls) == 1
    attempts = [p for p in Path(value.root).iterdir() if p.is_dir()]
    assert len(attempts) == 1 and list(attempts[0].iterdir()) == []


def test_lost_transport_result_is_static_no_receipt_no_retry(tmp_path):
    value = setup(tmp_path)
    calls = []
    def unknown(request):
        calls.append(request)
        raise RuntimeError("API secret provider response must stay private")
    with pytest.raises(own.PrivateProbeRejected, match="^demo_private_probe_rejected$"):
        invoke(value, unknown)
    assert len(calls) == 1
    assert list(Path(value.root).glob("*/receipt.json")) == []


def test_unknown_receipt_fsync_never_resends_or_reports_success(tmp_path, monkeypatch):
    value = setup(tmp_path)
    calls = []
    original = os.fsync
    def fsync(fd):
        if stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("private fsync error")
        return original(fd)
    monkeypatch.setattr(own.os, "fsync", fsync)
    with pytest.raises(own.PrivateProbeRejected):
        invoke(value, lambda request: calls.append(request) or reply(request))
    assert len(calls) == 1
    # An unknown write may leave a receipt: it is never authority or a retry trigger.
    assert len(list(Path(value.root).glob("*/receipt.json"))) == 1


@pytest.mark.parametrize("bad", [[], ["--other"], ["--native-demo-probe", "accidental-secret"]])
def test_default_or_unknown_cli_args_are_static_before_input_files_network(monkeypatch, capsys, bad):
    monkeypatch.setattr(own, "PrivateProbeSetup", lambda *a: pytest.fail("no files"))
    monkeypatch.setattr(own.getpass, "getpass", lambda *a: pytest.fail("no input"))
    monkeypatch.setattr(own, "HTTPSDemoReadTransport", lambda: pytest.fail("no network"))
    assert own.main(bad) == 1
    output = capsys.readouterr()
    assert output.out == "" and output.err == own.ERROR+"\n"


def terminal(monkeypatch, tmp_path):
    root = setup(tmp_path).root
    monkeypatch.setattr(own, "ROOT", root)
    monkeypatch.setattr(own, "OWNER_UID", os.getuid())
    for stream in (own.sys.stdin, own.sys.stdout, own.sys.stderr):
        monkeypatch.setattr(stream, "isatty", lambda: True)


def test_redirected_tty_rejects_before_getpass_or_file(monkeypatch):
    monkeypatch.setattr(own, "OWNER_UID", os.getuid())
    monkeypatch.setattr(own.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(own, "PrivateProbeSetup", lambda *a: pytest.fail("no files"))
    monkeypatch.setattr(own.getpass, "getpass", lambda *a: pytest.fail("no input"))
    assert own.main(["--native-demo-probe"]) == 1


def test_getpass_visible_fallback_warning_and_declined_origin_stop(monkeypatch, tmp_path):
    terminal(monkeypatch, tmp_path)
    monkeypatch.setattr(own, "HTTPSDemoReadTransport", lambda: pytest.fail("no network"))
    monkeypatch.setattr(own.getpass, "getpass", lambda *a: "NO")
    assert own.main(["--native-demo-probe"]) == 1
    def fallback(*args):
        warnings.warn("getpass cannot control echo", getpass.GetPassWarning)
        pytest.fail("visible fallback input must not run")
    monkeypatch.setattr(own.getpass, "getpass", fallback)
    assert own.main(["--native-demo-probe"]) == 1


def test_tty_handoff_is_explicit_and_success_is_redacted(monkeypatch, tmp_path, capsys):
    terminal(monkeypatch, tmp_path)
    answers = iter(("DEMO", "synthetic-probe-api", "synthetic-probe-secret-ß", "synthetic-probe-pass"))
    monkeypatch.setattr(own.getpass, "getpass", lambda *a: next(answers))
    marker = object()
    monkeypatch.setattr(own, "HTTPSDemoReadTransport", lambda: marker)
    def captured(value, credentials, **kwargs):
        assert type(value) is own.PrivateProbeSetup
        assert credentials._secret_key == TRIPLE._secret_key
        assert kwargs == dict(confirmed_demo_origin=True, transport=marker)
    monkeypatch.setattr(own, "probe", captured)
    assert own.main(["--native-demo-probe"]) == 0
    output = capsys.readouterr()
    assert own.SUCCESS in output.out and "synthetic-probe" not in output.out
    assert output.err == ""


def test_actual_linux_controlling_tty_hides_credentials_and_publishes_private_receipt(tmp_path):
    value = setup(tmp_path)
    code = """
import json, sys
from investalo_bitget import ReadResponse
from investalo_credential_store import demo_private_probe as own
own.ROOT = sys.argv[1]
def transport(request):
    return ReadResponse(200, json.dumps(dict(code="00000",
        requestTime=int(request.headers["ACCESS-TIMESTAMP"]), data=dict(
        userId="123456", parentId=0, ips="192.0.2.18", authorities=["coor","cpor"]))).encode())
own.HTTPSDemoReadTransport = lambda: transport
raise SystemExit(own.main(["--native-demo-probe"]))
"""
    pid, master = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-c", code, value.root])
    output = bytearray()
    exited = False
    try:
        deadline = time.monotonic()+10
        prompts = iter((
            (b"Type DEMO to confirm: ", b"DEMO\n"),
            (b"Demo API key: ", TRIPLE._api_key.encode()+b"\n"),
            (b"Demo API secret: ", TRIPLE._secret_key+b"\n"),
            (b"Demo passphrase: ", TRIPLE._passphrase.encode()+b"\n"),
        ))
        pending = next(prompts)
        while time.monotonic() < deadline and len(output) < 16384:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                output.extend(chunk)
                if pending is not None and pending[0] in output:
                    os.write(master, pending[1])
                    pending = next(prompts, None)
            if own.SUCCESS.encode() in output:
                break
        assert pending is None and own.SUCCESS.encode() in output
        observed, status = os.waitpid(pid, 0)
        exited = True
        assert observed == pid and os.waitstatus_to_exitcode(status) == 0
        assert all(part not in output for part in (
            TRIPLE._api_key.encode(), TRIPLE._secret_key, TRIPLE._passphrase.encode()))
        paths = list(Path(value.root).glob("*/receipt.json"))
        assert len(paths) == 1 and json.loads(paths[0].read_text())["order_dispatch"] is False
    finally:
        os.close(master)
        if not exited:
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
