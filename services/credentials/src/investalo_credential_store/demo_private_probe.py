"""Opt-in operator TTY identity probe; no platform registration or orders."""
from __future__ import annotations

import getpass
import fcntl
import hashlib
import json
import os
import secrets
import stat
import sys
import time
import warnings
from types import MappingProxyType
from uuid import UUID, uuid4

from investalo_bitget import Credentials
from investalo_bitget.futures_demo_read import HTTPSDemoReadTransport

from .demo_native_provisioning import (
    DemoNativeProvisioner, DemoOriginApproval, make_demo_origin_record,
)
from .development_runtime import _checked_file, _object, _invalid_constant
from .demo_native_provisioning import _stamp
from .models import _PrivateImmutable

ROOT = "/run/demo-native-probe"
OWNER_UID = 10003
SCHEMA = "investalo-demo-private-probe/1"
FIELDS = frozenset(("schema", "tenant_id", "user_id", "account_id", "connection_id",
                   "broker_uid", "parent_uid", "egress_ip", "authorities"))
ERROR = "Demo identity probe rejected; no retry or platform change."
SUCCESS = "Demo identity checked. Private receipt saved; full account acceptance remains pending."


class PrivateProbeRejected(ValueError):
    def __init__(self):
        super().__init__("demo_private_probe_rejected")


class PrivateProbeSetup(_PrivateImmutable):
    __slots__ = ("root", "_uid", "_original", "_values", "sha256")

    def __init__(self, root, *, owner_uid=OWNER_UID):
        try:
            if type(root) is not str or not root.startswith("/") or type(owner_uid) is not int:
                raise ValueError()
            object.__setattr__(self, "root", root)
            object.__setattr__(self, "_uid", owner_uid)
            raw, values, stamp = self._read()
            object.__setattr__(self, "_original", stamp)
            values["authorities"] = tuple(values["authorities"])
            object.__setattr__(self, "_values", MappingProxyType(values))
            object.__setattr__(self, "sha256", hashlib.sha256(raw).hexdigest())
        except Exception:
            raise PrivateProbeRejected() from None

    def _read(self):
        directory = None
        try:
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            root = os.fstat(directory)
            if root.st_uid != self._uid or stat.S_IMODE(root.st_mode) != 0o700:
                raise ValueError()
            with _checked_file(self.root+"/setup.json", limit=4096, owner=self._uid) as (fd, raw):
                value = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant)
                if type(value) is not dict or set(value) != FIELDS or value["schema"] != SCHEMA:
                    raise ValueError()
                ids = {}
                for field in ("tenant_id", "user_id", "account_id", "connection_id"):
                    text = value[field]
                    if type(text) is not str or str(UUID(text)) != text:
                        raise ValueError()
                    ids[field] = UUID(text)
                # Reuse the origin contract's exact UID/parent/IP/read vocabulary.
                checked = DemoOriginApproval(json.dumps(dict(
                    schema="investalo-demo-origin-approval/1",
                    origin="operator_attested_bitget_demo_mode", attestation_id=str(UUID(int=1)),
                    **{k: value[k] for k in FIELDS-{"schema", "connection_id"}},
                    approved_ms=0, expires_ms=1, credential_mac="0"*64),
                    sort_keys=True, separators=(",", ":")).encode())
                stamp = ((root.st_dev, root.st_ino, root.st_mode, root.st_uid, root.st_gid),
                         _stamp(os.fstat(fd)), hashlib.sha256(raw).hexdigest())
                if hasattr(self, "_original") and stamp != self._original:
                    raise ValueError()
                values = dict(owner=checked.owner, account_id=ids["account_id"],
                    connection_id=ids["connection_id"], broker_uid=checked.broker_uid,
                    parent_uid=checked.parent_uid, egress_ip=checked.egress_ip,
                    authorities=list(checked.authorities))
            return raw, values, stamp
        except Exception:
            raise PrivateProbeRejected() from None
        finally:
            if directory is not None:
                os.close(directory)

    def check(self):
        self._read()


def _receipt(directory, record):
    """Create-only private result; failed/unknown writes never trigger a GET retry."""
    fd = None
    try:
        wire = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        fd = os.open("receipt.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW |
                     os.O_CLOEXEC, 0o600, dir_fd=directory)
        offset = 0
        while offset < len(wire):
            written = os.write(fd, wire[offset:])
            if written <= 0:
                raise ValueError()
            offset += written
        os.fsync(fd)
        os.close(fd)
        fd = os.open("receipt.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
        metadata = os.fstat(fd)
        if (not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_uid != os.geteuid() or metadata.st_nlink != 1
                or metadata.st_size != len(wire) or os.read(fd, len(wire)+1) != wire):
            raise ValueError()
        os.fsync(directory)
    finally:
        if fd is not None:
            os.close(fd)


def probe(setup, credentials, *, confirmed_demo_origin, transport,
          milliseconds=lambda: time.time_ns()//1_000_000):
    """One independently declared operator probe, not a DB/account permission grant."""
    root = attempt = None
    try:
        if (type(setup) is not PrivateProbeSetup or type(credentials) is not Credentials
                or confirmed_demo_origin is not True or not callable(transport)):
            raise ValueError()
        setup.check()
        root = os.open(setup.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        fcntl.flock(root, fcntl.LOCK_EX | fcntl.LOCK_NB)
        setup.check()
        run_id = str(uuid4())
        os.mkdir(run_id, mode=0o700, dir_fd=root)
        attempt = os.open(run_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=root)
        os.fsync(root)
        values = setup._values
        started = milliseconds()
        provenance_key = secrets.token_bytes(32)  # Ephemeral; not KEK or assertion authority.
        approval = DemoOriginApproval(make_demo_origin_record(credentials=credentials,
            provenance_key=provenance_key, **{k: v for k, v in values.items() if k != "connection_id"},
            attestation_id=UUID(run_id), approved_ms=started, expires_ms=started+60_000,
            created_in_bitget_demo_mode=True))
        responses = []

        def read():
            setup.check()
            return approval

        def receive(request):
            before = milliseconds()
            response = transport(request)
            after = milliseconds()
            responses.append(dict(target=request.target, response_sha256=hashlib.sha256(response.body).hexdigest(),
                                  started_ms=before, returned_ms=after))
            return response

        provision = DemoNativeProvisioner(read_approval=read, load_provenance_key=lambda: provenance_key,
            transport=receive, milliseconds=milliseconds)
        spec = provision(credentials, owner=values["owner"], account_id=values["account_id"],
            connection_id=values["connection_id"], expires_ms=started+60_000)
        setup.check()
        if len(responses) != 1:
            raise ValueError()
        record = dict(schema="investalo-demo-private-probe-receipt/1", run_id=run_id,
            setup_sha256=setup.sha256, status="identity_checked", spec=spec.record(),
            response=responses[0], origin="operator_attested_bitget_demo_mode",
            native_demo_creation_verified=False, full_account_acceptance_verified=False,
            platform_registration=False, order_dispatch=False)
        _receipt(attempt, record)
        setup.check()
        return run_id
    except Exception:
        raise PrivateProbeRejected() from None
    finally:
        if attempt is not None:
            os.close(attempt)
        if root is not None:
            os.close(root)


def main(argv=None):
    try:
        argv = sys.argv[1:] if argv is None else argv
        # No argument parser that could echo an accidentally supplied key.
        if (argv != ["--native-demo-probe"] or os.geteuid() != OWNER_UID
                or not all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr))):
            raise ValueError()
        setup = PrivateProbeSetup(ROOT)
        print("One Demo read only. Confirm this key was created in Bitget Demo mode.", flush=True)
        # getpass must never fall back to visible/redirected input.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            if getpass.getpass("Type DEMO to confirm: ") != "DEMO":
                raise ValueError()
            credentials = Credentials(getpass.getpass("Demo API key: "),
                getpass.getpass("Demo API secret: "), getpass.getpass("Demo passphrase: "))
        probe(setup, credentials, confirmed_demo_origin=True, transport=HTTPSDemoReadTransport())
        print(SUCCESS, flush=True)
        return 0
    except (Exception, KeyboardInterrupt):
        print(ERROR, file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
