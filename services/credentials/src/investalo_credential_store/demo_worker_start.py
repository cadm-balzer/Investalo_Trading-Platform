"""Actual original-intent -> restricted worker store -> native startup read.

This entry point is strictly GET-only. It never creates a financial journal,
consumes an order grant, sets account parameters, or installs a trading loop.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
import sys
import threading
import time

from investalo_bitget.futures_demo import DemoBinding, DemoRejected
from .demo_worker_authorization import verify_worker_intent
from .demo_worker_store import DemoWorkerCredentialStore
from .demo_start_account import NativeStartAccountSource


@dataclass(frozen=True)
class DemoWorkerStartReport:
    control_revision: int
    action: str
    basket_limit: int
    assets: tuple[str, ...]
    native: object
    execution_enabled: bool = False


class DemoWorkerStartProbe:
    def __init__(self, config, context, *, read_control, intent_key, connect, keyring,
                 installation_guard, transport=None, milliseconds=lambda: time.time_ns()//1_000_000,
                 policy_factory=None):
        if not all(callable(p) for p in (read_control, connect, keyring, installation_guard, milliseconds)):
            raise DemoRejected("original_worker_start_ports_required")
        self.config, self.context = config, context
        self.read_control, self.intent_key, self.connect = read_control, intent_key, connect
        self.keyring, self.installation_guard, self.transport = keyring, installation_guard, transport
        self.now, self.lock, self.pid = milliseconds, threading.Lock(), os.getpid()
        if policy_factory is not None and not callable(policy_factory):
            raise DemoRejected("own_demo_policy_factory_required")
        self.policy_factory = policy_factory

    def read(self):
        if self.pid != os.getpid() or not self.lock.acquire(blocking=False):
            raise DemoRejected("worker_start_probe_busy")
        try:
            self.installation_guard()
            raw = self.read_control()
            # UUID/connection values in this packet are trusted only after its
            # independent Dashboard signature is verified below.
            packet = json.loads(raw)
            binding_fields = json.loads(packet["payload"])["binding"]
            from uuid import UUID
            from investalo_bitget import OwnerContext
            binding = DemoBinding(OwnerContext(self.config["tenant_id"], self.config["user_id"]),
                self.config["account_id"], UUID(binding_fields["connection_id"]), self.config["broker_uid"])
            original = verify_worker_intent(raw, self.intent_key, binding=binding, now_ms=self.now())

            def guard(candidate=original):
                self.installation_guard()
                current = verify_worker_intent(self.read_control(), self.intent_key,
                                               binding=binding, now_ms=self.now())
                if current != original or candidate != original:
                    raise DemoRejected("original_worker_start_changed")

            store = DemoWorkerCredentialStore(self.context, original,
                oidc_issuer=self.config["oidc_issuer"], connect=self.connect, control_guard=guard,
                expires_ms=self.now()+30000, milliseconds=self.now)
            snapshot = store.read_snapshot(binding, binding.owner)
            if (snapshot.spec.parent_uid != self.config["parent_uid"]
                    or snapshot.spec.egress_ip != self.config["egress_ip"]):
                raise DemoRejected("worker_private_identity_changed")
            provider = store.provider(snapshot.spec, load_keyring=self.keyring)
            source = NativeStartAccountSource(provider, guard=guard, shared_lock=threading.Lock(),
                ip_binding=self.config["ip_binding"], transport=self.transport, milliseconds=self.now,
                policy=self.policy_factory(snapshot) if self.policy_factory else None)
            native = source.read(context=binding.owner)
            guard()
            return DemoWorkerStartReport(original.revision, original.action, original.basket_limit,
                                         original.assets, native)
        finally:
            self.lock.release()


def main(argv=None):
    if (list(sys.argv[1:] if argv is None else argv) != ["--bitget-demo-worker-start-inspect"]
            or os.environ.get("DEMO_H1_START_INSPECTION_ENABLED") != "1" or os.geteuid() != 10003
            or any(name.startswith("PG") for name in os.environ)):
        raise SystemExit("Demo worker inspection unavailable")
    from .demo_trading_runtime import configuration, ROOT, LOGIN, KEY_VERSION
    from .development_runtime import _read
    from .models import StoreContext
    from investalo_credentials import KEKRing
    import psycopg
    control_root = "/run/demo-worker-start"
    raw_config = _read(ROOT+"/config", limit=4096)
    config = configuration(json.loads(raw_config))
    original_control = _read(control_root+"/intent", limit=8192)
    intent_key = _read(control_root+"/intent-key", limit=32, exact=32)
    expected_kek = config["kek_sha256"]

    def guard():
        if (_read(ROOT+"/config", limit=4096) != raw_config
                or _read(control_root+"/intent", limit=8192) != original_control
                or _read(control_root+"/intent-key", limit=32, exact=32) != intent_key):
            raise DemoRejected("original_start_installation_changed")

    def keyring():
        guard()
        key = _read(ROOT+"/kek", limit=32, exact=32)
        if hashlib.sha256(key).hexdigest() != expected_kek:
            raise DemoRejected("worker_kek_changed")
        return KEKRing(((KEY_VERSION, key),), active_version=KEY_VERSION)

    password = _read(ROOT+"/database-password", limit=4096).decode("ascii")
    @contextmanager
    def connect():
        guard()
        with psycopg.connect(host="postgres", port=5432, dbname="investalo", user=LOGIN,
                password=password, sslmode="verify-full", sslrootcert="/run/secrets/local_ca_cert",
                connect_timeout=5, autocommit=False, gssencmode="disable",
                options="-c statement_timeout=10000 -c lock_timeout=5000") as db:
            yield db

    policy_factory = None
    if os.environ.get("DEMO_H1_APPROVED_UNKNOWN_NATIVE") == "1":
        from investalo_bitget.futures_demo_policy import ApprovedDemoStrategyPolicy
        policy_factory = lambda snapshot: ApprovedDemoStrategyPolicy(
            snapshot.spec.binding, snapshot.spec.credential_revision, snapshot.storage_version)
    result = DemoWorkerStartProbe(config, StoreContext(tenant_id=config["tenant_id"],
        user_id=config["user_id"], expected_login_role=LOGIN), read_control=lambda: original_control,
        intent_key=intent_key, connect=connect, keyring=keyring, installation_guard=guard,
        policy_factory=policy_factory).read()
    print(json.dumps(dict(schema="investalo-demo-h1-start-inspection/1", revision=result.control_revision,
        action=result.action, basket_limit=result.basket_limit, assets=result.assets,
        observed_at=result.native.observed_at.isoformat(), blockers=result.native.blockers,
        unconfirmed_fields=result.native.unconfirmed_fields,
        policy_digest=result.native.policy_digest,
        native_flat_account_confirmed=result.native.account is not None,
        equity=str(result.native.account.equity) if result.native.account else None,
        source_digest=result.native.source_digest, execution_enabled=False)))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Demo worker start not confirmed; private error withheld") from None
