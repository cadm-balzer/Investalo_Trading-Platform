"""Private operative Demo daemon. Original signed control, native Market only."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
from investalo_credentials import KEKRing
from investalo_bitget import OwnerContext
from investalo_bitget.futures_demo import DemoBinding, DemoRejected
from investalo_bitget.futures_demo_policy import ApprovedDemoStrategyPolicy
from investalo_bitget.futures_demo_warmup import DemoWarmupSource
from investalo_trading.futures_broker_journal import BrokerEntryJournal, _profile
from investalo_trading.futures_replay_journal import _open
from investalo_trading.futures_broker_bootstrap import BrokerFlatAccount
from investalo_workers.futures_demo_h1_worker import DemoH1Worker
from .demo_trading_runtime import configuration, ROOT, LOGIN, KEY_VERSION
from .development_runtime import _read
from .models import StoreContext
from .demo_worker_authorization import verify_worker_intent, DurableBasketConsumer
from .demo_worker_store import DemoWorkerCredentialStore
from .demo_start_account import NativeStartAccountSource
from .demo_h1_market import DemoH1MarketSource, native_profile, UNIVERSE
from .demo_h1_native import DemoH1NativeGuard
from .demo_basket_orders import BasketOrderDispatcher, HTTPSBasketReadTransport, HTTPSBasketTransport
from .demo_basket_margin import BasketNativeMarginSource
from .demo_basket_funding import BasketNativeFundingSource

STATE = Path("/app/demo-h1-state")
SETUP = "/run/demo-h1-worker"
CONTROL = "/run/demo-h1-control"
STATUS = Path("/app/demo-h1-status/status.json")
STATUS_SCHEMA = "investalo-demo-h1-worker-status/1"


def clock():
    return datetime.now(timezone.utc)


def atomic(path, raw, mode=0o600):
    temporary = path.with_name("."+uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        offset = 0
        while offset < len(raw):
            n = os.write(fd, raw[offset:])
            if n <= 0:
                raise OSError()
            offset += n
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    if path.read_bytes() != raw:
        raise OSError("worker write acknowledgement unknown")


class DemoH1Runtime:
    def __init__(self):
        if (os.geteuid() != 10003 or os.environ.get("DEMO_H1_WORKER_ENABLED") != "1"
                or any(k.startswith("PG") for k in os.environ)):
            raise DemoRejected("demo_h1_runtime_disabled")
        self.raw_config = _read(ROOT+"/config", limit=4096)
        self.config = configuration(json.loads(self.raw_config))
        self.raw_setup = _read(SETUP+"/config", limit=4096)
        setup = json.loads(self.raw_setup)
        if (set(setup) != {"schema", "connection_id", "storage_version", "intent_key_sha256", "approved_unknown_native"}
                or setup["schema"] != "investalo-demo-h1-worker/1" or setup["approved_unknown_native"] is not True
                or type(setup["storage_version"]) is not int or setup["storage_version"] < 1):
            raise DemoRejected("private_demo_h1_setup_unconfirmed")
        self.key = _read(SETUP+"/intent-key", limit=32, exact=32)
        if hashlib.sha256(self.key).hexdigest() != setup["intent_key_sha256"]:
            raise DemoRejected("private_demo_control_key_changed")
        self.owner = OwnerContext(self.config["tenant_id"], self.config["user_id"])
        self.binding = DemoBinding(self.owner, self.config["account_id"],
            UUID(setup["connection_id"]), self.config["broker_uid"])
        self.storage = setup["storage_version"]
        self.policy = ApprovedDemoStrategyPolicy(self.binding, 1, self.storage)
        self.context = StoreContext(tenant_id=self.owner.tenant_id, user_id=self.owner.user_id, expected_login_role=LOGIN)
        self.control_path = CONTROL+"/"+str(self.owner.tenant_id)+"."+str(self.binding.account_id)+".json"
        self.password = _read(ROOT+"/database-password", limit=4096).decode("ascii")
        self.journal, self.consumer, self.worker = None, None, None
        self.warmup, self.market = DemoWarmupSource(), DemoH1MarketSource()
        self.mutex = threading.Lock()
        self.last_control = None
        self.install_guard()
        if (STATE.is_symlink() or STATE.stat().st_uid != 10003 or (STATE.stat().st_mode & 0o7777) != 0o700):
            raise DemoRejected("private_worker_state_required")
        for n in ("consumed", "configuration"):
            (STATE/n).mkdir(mode=0o700, exist_ok=True)
        if (STATE/"basket.jsonl").exists():
            receipt_path = STATE/"receipt.json"
            if not receipt_path.exists():
                raise DemoRejected("native_worker_checkpoint_missing")
            wire = json.loads(receipt_path.read_bytes())
            self.verify_seal(wire, "native-worker-receipt/1")
            # Read only the bounded original header. Full durable replay follows.
            with _open(STATE/"basket.jsonl", create=False) as f:
                header = json.loads(f.readline(1024*1024))
            original = header
            profile = _profile(original["profile"])
            self.journal = BrokerEntryJournal.restore(STATE/"basket.jsonl",
                journal_id=UUID(original["journal_id"]), profile_digest=profile.profile_digest,
                minimum_receipt=json.loads(wire["payload"]))
            self.attach()

    def install_guard(self):
        if (os.environ.get("DEMO_H1_WORKER_ENABLED") != "1"
                or _read(ROOT+"/config", limit=4096) != self.raw_config
                or _read(SETUP+"/config", limit=4096) != self.raw_setup
                or _read(SETUP+"/intent-key", limit=32, exact=32) != self.key):
            raise DemoRejected("worker_installation_changed")

    def control(self):
        self.install_guard()
        raw = _read(self.control_path, limit=8192, owner=10002, mode=0o640)
        return verify_worker_intent(raw, self.key, binding=self.binding, now_ms=time.time_ns()//1_000_000)

    def keyring(self):
        self.install_guard()
        key = _read(ROOT+"/kek", limit=32, exact=32)
        if hashlib.sha256(key).hexdigest() != self.config["kek_sha256"]:
            raise DemoRejected("worker_kek_changed")
        return KEKRing(((KEY_VERSION, key),), active_version=KEY_VERSION)

    @contextmanager
    def connect(self):
        self.install_guard()
        with psycopg.connect(host="postgres", port=5432, dbname="investalo", user=LOGIN,
                password=self.password, sslmode="verify-full", sslrootcert="/run/secrets/local_ca_cert",
                connect_timeout=5, autocommit=False, gssencmode="disable",
                options="-c statement_timeout=10000 -c lock_timeout=5000") as db:
            yield db

    def ports(self, control):
        if control.storage_version != self.storage:
            raise DemoRejected("worker_credential_authorization_changed")
        def guard(candidate=control):
            if self.control() != control or candidate != control:
                raise DemoRejected("worker_control_changed")
        store = DemoWorkerCredentialStore(self.context, control, oidc_issuer=self.config["oidc_issuer"],
            connect=self.connect, control_guard=guard, expires_ms=time.time_ns()//1_000_000+60000)
        snapshot = store.read_snapshot(self.binding, self.owner)
        if snapshot.spec.parent_uid != self.config["parent_uid"] or snapshot.spec.egress_ip != self.config["egress_ip"]:
            raise DemoRejected("worker_native_identity_changed")
        provider = store.provider(snapshot.spec, load_keyring=self.keyring)
        read = HTTPSBasketReadTransport()
        margin = BasketNativeMarginSource(transport=read, policy=self.policy)
        native = DemoH1NativeGuard(provider, self.policy, guard)
        dispatcher = None if self.journal is None else BasketOrderDispatcher(
            self.journal, provider, read_transport=read, order_transport=HTTPSBasketTransport(),
            native_guard=guard, account_guard=lambda i, r, o: native.admit(self.journal, i, r, o),
            authorize_once=self.consumer, margin_source=margin, funding_source=BasketNativeFundingSource(margin),
            shared_lock=self.mutex, ip_binding=self.config["ip_binding"], enabled=True)
        return SimpleNamespace(owner=self.owner, provider=provider, native=native, guard=guard,
                               market=self.market, dispatcher=dispatcher)

    def actor_guard(self, intent):
        self.ports(intent).guard()

    def attach(self):
        self.consumer = DurableBasketConsumer(STATE/"consumed", binding=self.binding, intent_key=self.key,
            read_control=lambda: _read(self.control_path, limit=8192, owner=10002, mode=0o640),
            actor_guard=self.actor_guard, journal=self.journal)
        self.worker = DemoH1Worker(self.journal, self.consumer, self.warmup, clock)

    def seal(self, value, purpose):
        payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
        return json.dumps(dict(payload=payload,
            mac=hmac.new(self.key, (purpose+"\0"+payload).encode(), hashlib.sha256).hexdigest())).encode()

    def verify_seal(self, wire, purpose):
        if not hmac.compare_digest(wire["mac"], hmac.new(self.key,
            (purpose+"\0"+wire["payload"]).encode(), hashlib.sha256).hexdigest()):
            raise DemoRejected("worker_checkpoint_signature_unconfirmed")

    def save(self):
        if self.journal:
            atomic(STATE/"receipt.json", self.seal(self.journal.receipt, "native-worker-receipt/1"))

    def status(self, state, detail, enabled=False):
        control = self.last_control
        if control is None:
            return
        value = dict(schema=STATUS_SCHEMA, tenant_id=str(control.tenant_id), account_id=str(control.account_id),
            connection_id=str(control.connection_id), storage_version=control.storage_version, auth_epoch=control.auth_epoch,
            control_revision=control.revision, state=state, detail=detail, execution_enabled=enabled,
            observed_at=clock().isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            journal_revision=self.journal.state.revision if self.journal else 0)
        atomic(STATUS, self.seal(value, STATUS_SCHEMA), mode=0o640)

    def once(self):
        control = self.control()
        self.last_control = control
        if self.journal is None:
            if control.action != "start":
                self.status("paused", "buys_paused_positions_managed")
                return
            ports = self.ports(control)
            self.status("waiting", "native_profile_preparation")
            ports.native.prepare_profiles(control.assets, STATE/"configuration", self.config["ip_binding"])
            # Warm history first; current financial evidence is obtained last.
            self.warmup.collect(UNIVERSE, clock().replace(minute=0, second=0, microsecond=0))
            market = self.market.read()
            source = NativeStartAccountSource(ports.provider, guard=ports.guard, shared_lock=self.mutex,
                ip_binding=self.config["ip_binding"], policy=self.policy)
            evidence = source.read(context=self.owner)
            if evidence.account is None:
                raise DemoRejected("native_initial_account_not_flat")
            profile = native_profile(control, evidence.account, market, self.policy)
            at = clock()
            if evidence.account.wallet_at.replace(minute=0, second=0, microsecond=0) != self.warmup.window.end:
                raise DemoRejected("native_initial_hour_changed")
            self.journal = BrokerEntryJournal.create_current(STATE/"basket.jsonl", profile,
                market.trade, market.marks, evidence.account, at, journal_id=uuid4())
            self.save()
            self.attach()
        ports = self.ports(control)
        result = self.worker.run_once(ports)
        self.save()
        self.status(result.state, result.detail, result.execution_enabled)


def main():
    if sys.argv[1:] != ["--bitget-demo-h1-worker"]:
        raise SystemExit("Demo H1 worker unavailable")
    runtime = DemoH1Runtime()
    while True:
        started = time.monotonic()
        try:
            runtime.once()
        except Exception as error:
            code = str(error)
            diagnostic = dict(type=type(error).__name__,
                code=code if code.isascii() and code.replace("_", "").isalnum() and len(code) <= 128
                     else "worker_check_unconfirmed", at=clock().isoformat())
            atomic(STATE/"diagnostic.json", json.dumps(diagnostic).encode())
            runtime.save()  # If the writer is uncertain, restart and replay instead of using memory.
            runtime.status("blocked", "native_check_unconfirmed")
        time.sleep(max(.1, 6-(time.monotonic()-started)))


if __name__ == "__main__":
    main()
