"""Explicit Demo-origin approval plus a fixed signed native identity probe.

Origin is a trusted operator attestation, not a broker-certified creation proof.
No launcher, browser intake, credentials file, DB write or order dispatch.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import threading
import time
from types import MappingProxyType
from uuid import UUID

from investalo_bitget import Credentials, OwnerContext
from investalo_bitget import parse
from investalo_bitget.futures_demo import DemoBinding, clock, digest
from investalo_bitget.futures_demo_read import DemoReadCredential, SignedDemoReadRequest
from investalo_bitget.models import AccountBinding, READ_AUTHORITIES

from .bitget_payload import encode_credentials
from .demo_secret_provider import DemoSecretSpec
from .models import _PrivateImmutable

SCHEMA = "investalo-demo-origin-approval/1"
ORIGIN = "operator_attested_bitget_demo_mode"
APPROVAL_MS = 900_000
PROBE_MS = 5_000
MAX_BYTES = 8192
FIELDS = frozenset(("schema", "origin", "attestation_id", "tenant_id", "user_id",
    "account_id", "broker_uid", "parent_uid", "egress_ip", "authorities",
    "approved_ms", "expires_ms", "credential_mac"))


class DemoProvisioningRejected(ValueError):
    def __init__(self):
        super().__init__("demo_provisioning_rejected")


def _canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _key(value):
    if type(value) is not bytes or len(value) != 32:
        raise DemoProvisioningRejected()
    return value


def _mac(record, credentials, key):
    metadata = _canonical({k: v for k, v in record.items() if k != "credential_mac"})
    payload = encode_credentials(credentials).reveal()
    # Dedicated operator key, full triple and all approval metadata; never a
    # public unkeyed fingerprint of an API secret or an ambiguous string join.
    return hmac.new(_key(key), b"investalo.demo.origin-approval/1\0" +
        len(metadata).to_bytes(4, "big") + metadata + payload, hashlib.sha256).hexdigest()


class DemoOriginApproval(_PrivateImmutable):
    __slots__ = ("_wire", "_record", "owner", "account_id", "broker_uid", "parent_uid",
                 "egress_ip", "authorities", "approved_ms", "expires_ms", "sha256")

    def __init__(self, wire):
        try:
            if type(wire) is not bytes or not 1 <= len(wire) <= MAX_BYTES:
                raise ValueError()
            def unique(pairs):
                record = {}
                for key, value in pairs:
                    if key in record:
                        raise ValueError()
                    record[key] = value
                return record
            raw = json.loads(wire, object_pairs_hook=unique,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if (type(raw) is not dict or set(raw) != FIELDS or wire != _canonical(raw)
                    or raw["schema"] != SCHEMA or raw["origin"] != ORIGIN):
                raise ValueError()
            ids = {}
            for field in ("tenant_id", "user_id", "account_id", "attestation_id"):
                value = raw[field]
                if type(value) is not str or str(UUID(value)) != value:
                    raise ValueError()
                ids[field] = UUID(value)
            owner = OwnerContext(ids["tenant_id"], ids["user_id"])
            checked = AccountBinding(owner, raw["broker_uid"], raw["parent_uid"],
                                     expected_egress_ip=raw["egress_ip"])
            rights = raw["authorities"]
            if (type(raw["parent_uid"]) is not str or checked.expected_egress_ip is None
                    or checked.expected_egress_ip != raw["egress_ip"]
                    or type(rights) is not list or any(type(v) is not str for v in rights)
                    or rights != sorted(set(rights)) or not set(rights) <= READ_AUTHORITIES
                    or not {"coor", "cpor"} <= set(rights)
                    or type(raw["credential_mac"]) is not str
                    or re.fullmatch("[0-9a-f]{64}", raw["credential_mac"]) is None):
                raise ValueError()
            approved, expires = clock(raw["approved_ms"]), clock(raw["expires_ms"])
            if not approved < expires <= approved + APPROVAL_MS:
                raise ValueError()
            raw["authorities"] = tuple(rights)
            for name, value in (("_wire", wire), ("_record", MappingProxyType(raw)), ("owner", owner),
                ("account_id", ids["account_id"]), ("broker_uid", checked.expected_uid),
                ("parent_uid", checked.expected_parent_id), ("egress_ip", raw["egress_ip"]),
                ("authorities", tuple(rights)), ("approved_ms", approved),
                ("expires_ms", expires), ("sha256", hashlib.sha256(wire).hexdigest())):
                object.__setattr__(self, name, value)
        except Exception:
            raise DemoProvisioningRejected() from None

    def check(self, credentials, key, *, owner, account_id, now_ms):
        try:
            if (type(credentials) is not Credentials or type(owner) is not OwnerContext
                    or owner != self.owner or type(account_id) is not UUID
                    or account_id != self.account_id
                    or not self.approved_ms <= clock(now_ms) < self.expires_ms
                    or not hmac.compare_digest(self._record["credential_mac"],
                                               _mac(self._record, credentials, key))):
                raise ValueError()
        except Exception:
            raise DemoProvisioningRejected() from None


def make_demo_origin_record(*, credentials, provenance_key, owner, account_id,
                           broker_uid, parent_uid, egress_ip, authorities,
                           attestation_id, approved_ms, expires_ms,
                           created_in_bitget_demo_mode):
    """Trusted setup only; caller must establish Demo origin independently.

    Returned private bytes contain metadata and a keyed MAC, never the triple.
    This function cannot independently certify the operator's statement.
    """
    try:
        if (created_in_bitget_demo_mode is not True or type(owner) is not OwnerContext
                or type(account_id) is not UUID or type(attestation_id) is not UUID):
            raise ValueError()
        record = dict(schema=SCHEMA, origin=ORIGIN, attestation_id=str(attestation_id),
            tenant_id=str(owner.tenant_id), user_id=str(owner.user_id), account_id=str(account_id),
            broker_uid=broker_uid, parent_uid=parent_uid, egress_ip=egress_ip,
            authorities=authorities, approved_ms=approved_ms, expires_ms=expires_ms)
        record["credential_mac"] = _mac(record, credentials, provenance_key)
        wire = _canonical(record)
        DemoOriginApproval(wire)
        return wire
    except Exception:
        raise DemoProvisioningRejected() from None


def _stamp(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid,
            value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _directory_identity(descriptor):
    value = os.fstat(descriptor)
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid)


class PrivateDemoOriginReader(_PrivateImmutable):
    """Original absolute directory/file, private modes and pinned content.

    No symbolic links in any path component, hardlinks, FIFOs or file rotation.
    Deletion/replacement/mutation denies the next check. Explicit setup must
    create a new reader for a separately approved record.
    """
    __slots__ = ("_path", "_uid", "_sha", "_original", "_pid")

    def __init__(self, path, *, owner_uid, expected_sha256):
        try:
            if (type(path) is not str or not path.startswith("/")
                    or len(path.split("/")) < 3
                    or any(p in ("", ".", "..") for p in path.split("/")[1:])
                    or type(owner_uid) is not int or owner_uid < 0
                    or type(expected_sha256) is not str
                    or re.fullmatch("[0-9a-f]{64}", expected_sha256) is None):
                raise ValueError()
            for name, value in (("_path", path), ("_uid", owner_uid),
                                ("_sha", expected_sha256), ("_pid", os.getpid())):
                object.__setattr__(self, name, value)
            _, stamps = self._read()
            object.__setattr__(self, "_original", stamps)
        except Exception:
            raise DemoProvisioningRejected() from None

    def _read(self):
        descriptors = []
        try:
            if os.getpid() != self._pid:
                raise ValueError()
            parts = self._path.split("/")[1:]
            current = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            descriptors.append(current)
            for part in parts[:-1]:
                current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                                  os.O_CLOEXEC, dir_fd=current)
                descriptors.append(current)
            root = os.fstat(current)
            if root.st_uid != self._uid or stat.S_IMODE(root.st_mode) != 0o700:
                raise ValueError()
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK |
                         os.O_CLOEXEC, dir_fd=current)
            descriptors.append(fd)
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != self._uid
                    or stat.S_IMODE(before.st_mode) != 0o400 or before.st_nlink != 1
                    or not 1 <= before.st_size <= MAX_BYTES):
                raise ValueError()
            chunks, size = [], 0
            while size <= MAX_BYTES:
                chunk = os.read(fd, MAX_BYTES + 1 - size)
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            wire = b"".join(chunks)
            ancestors = tuple(_directory_identity(d) for d in descriptors[:-1])
            stamps = (_stamp(root), _stamp(before), ancestors)
            if (len(wire) != before.st_size or _stamp(os.fstat(fd)) != stamps[1]
                    or _stamp(os.fstat(current)) != stamps[0]
                    or tuple(_directory_identity(d) for d in descriptors[:-1]) != ancestors
                    or hasattr(self, "_original") and stamps != self._original
                    or not hmac.compare_digest(hashlib.sha256(wire).hexdigest(), self._sha)):
                raise ValueError()
            approval = DemoOriginApproval(wire)
            # Rewalk original names as well as checking held FDs: a replaced
            # pathname cannot borrow the still-open approved inode.
            if (_stamp(os.stat(self._path, follow_symlinks=False)) != stamps[1]
                    or _stamp(os.stat(os.path.dirname(self._path), follow_symlinks=False)) != stamps[0]):
                raise ValueError()
            return approval, stamps
        except Exception:
            raise DemoProvisioningRejected() from None
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    def __call__(self):
        return self._read()[0]


class DemoNativeProvisioner(_PrivateImmutable):
    """Callable for DemoPasskeyOnboarding.provision; one GET, no fallback/retry.

    Trusted setup supplies the approval reader and a separate 32-byte MAC key.
    A valid native reply proves identity/rights/IP only, not Demo key creation.
    """
    __slots__ = ("_read", "_key", "_transport", "_milliseconds", "_lock", "_pid", "_last")

    def __init__(self, *, read_approval, load_provenance_key, transport,
                 milliseconds=lambda: time.time_ns() // 1_000_000):
        if not all(callable(v) for v in (read_approval, load_provenance_key, transport, milliseconds)):
            raise DemoProvisioningRejected()
        for name, value in (("_read", read_approval), ("_key", load_provenance_key),
            ("_transport", transport), ("_milliseconds", milliseconds),
            ("_lock", threading.Lock()), ("_pid", os.getpid()), ("_last", None)):
            object.__setattr__(self, name, value)

    def __call__(self, credentials, *, owner, account_id, connection_id, expires_ms):
        acquired = False
        try:
            if os.getpid() != self._pid:
                raise ValueError()
            acquired = self._lock.acquire(blocking=False)
            if not acquired:
                raise ValueError()
            start = clock(self._milliseconds())
            if (type(connection_id) is not UUID
                    or not start < clock(expires_ms) <= start + 60_000
                    or self._last is not None and start - self._last < 1000):
                raise ValueError()
            approval = self._read()
            if type(approval) is not DemoOriginApproval:
                raise ValueError()
            latest = start

            def guard():
                nonlocal latest
                now = clock(self._milliseconds())
                current = self._read()
                key = _key(self._key())
                after = clock(self._milliseconds())
                if (type(current) is not DemoOriginApproval or current._wire != approval._wire
                        or not latest <= now <= after <= start + PROBE_MS
                        or after >= expires_ms):
                    raise ValueError()
                current.check(credentials, key, owner=owner, account_id=account_id, now_ms=after)
                latest = after
                return after

            before = guard()
            binding = DemoBinding(owner, account_id, connection_id, approval.broker_uid)
            credential = DemoReadCredential(binding, credentials, approval.parent_uid,
                approval.egress_ip, approval.sha256, 1, min(expires_ms, approval.expires_ms))
            request = SignedDemoReadRequest(credential, timestamp_ms=before)
            object.__setattr__(self, "_last", before)  # Failed sends also consume the local interval.
            response = self._transport(request)
            after = guard()
            identity = parse.identity(response)
            delta = identity.server_time - parse.EPOCH
            native_ms = delta.days*86_400_000 + delta.seconds*1000 + delta.microseconds//1000
            if not 0 <= after - native_ms <= PROBE_MS:
                raise ValueError()
            AccountBinding(owner, approval.broker_uid, approval.parent_uid,
                           expected_egress_ip=approval.egress_ip).validate(owner, identity, require_ip=True)
            if identity.ip_whitelist != (approval.egress_ip,) or identity.authorities != approval.authorities:
                raise ValueError()
            checked = guard()
            if not 0 <= checked - native_ms <= PROBE_MS:
                raise ValueError()
            evidence = dict(schema="investalo-demo-provisioning-evidence/1",
                binding=binding.record(), origin=ORIGIN, origin_approval_sha256=approval.sha256,
                identity_response_sha256=hashlib.sha256(response.body).hexdigest(),
                native_time_ms=native_ms, checked_ms=checked,
                native_demo_creation_verified=False)
            return DemoSecretSpec(binding=binding, parent_uid=approval.parent_uid,
                egress_ip=approval.egress_ip, provisioning_digest=digest(evidence), credential_revision=1)
        except Exception:
            raise DemoProvisioningRejected() from None
        finally:
            if acquired:
                self._lock.release()
