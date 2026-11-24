"""Original actor/key guarded three-GET source. No order/grant/journal authority."""
import os
import hmac
from datetime import timedelta
import threading
import time

from investalo_bitget import parse
from investalo_bitget.models import AccountBinding
from investalo_bitget.demo_trading_identity import trading_identity
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_bootstrap import native_start_account
from investalo_bitget.futures_demo_read import DemoReadCredential, SignedDemoReadRequest, HTTPSDemoReadTransport
from .demo_trading_provider import SealedDemoTradingProvider


class NativeStartAccountSource:
    def __init__(self, provider, *, guard, shared_lock, ip_binding, transport=None,
                 milliseconds=lambda: time.time_ns()//1_000_000):
        if (type(provider) is not SealedDemoTradingProvider or not callable(guard)
                or shared_lock is None or ip_binding not in ("single_ip", "unavailable_in_demo")
                or not callable(milliseconds) or transport is not None and not callable(transport)):
            raise DemoRejected("original_native_start_source_required")
        self.provider, self.guard, self.lock = provider, guard, shared_lock
        self.ip_binding, self.transport = ip_binding, transport or HTTPSDemoReadTransport(timeout_seconds=3)
        self.now, self.pid, self.last = milliseconds, os.getpid(), None

    def read(self, *, context):
        if self.pid != os.getpid() or not self.lock.acquire(blocking=False):
            raise DemoRejected("native_start_source_busy_or_forked")
        try:
            binding = self.provider._spec.binding
            binding.check(context)
            started, previous_start = self.now(), self.last
            if previous_start is not None and started-previous_start < 1000:
                raise DemoRejected("native_start_source_rate_limited")
            self.last = started
            self.guard()
            original = self.provider(binding, context)
            spec = original.spec
            credential = DemoReadCredential(binding, original.credentials, spec.parent_uid,
                spec.egress_ip, spec.provisioning_digest, spec.credential_revision, original.expires_ms)

            def check():
                self.guard()
                current = self.provider(binding, context)
                declaration = DemoReadCredential(binding, current.credentials, spec.parent_uid,
                    spec.egress_ip, spec.provisioning_digest, spec.credential_revision, current.expires_ms)
                if (current.spec.record() != spec.record() or not hmac.compare_digest(
                        declaration.fingerprint(), credential.fingerprint())
                        or not 0 <= self.now()-started <= 5000):
                    raise DemoRejected("native_start_actor_key_or_cohort_changed")

            last_get = None
            def get(axis):
                nonlocal last_get
                if last_get is not None:
                    time.sleep(max(0, .11-(time.monotonic()-last_get)))
                check()
                last_get = time.monotonic()
                result = self.transport(SignedDemoReadRequest(credential, timestamp_ms=self.now(), axis=axis))
                check()
                _, at = parse.envelope(result)
                at_ms = int((at-parse.EPOCH)//timedelta(milliseconds=1))
                if not 0 <= self.now()-at_ms <= 5000:
                    raise DemoRejected("native_start_response_stale")
                return result

            identity = trading_identity(get("identity"))
            bound = self.ip_binding == "single_ip"
            AccountBinding(context, binding.broker_uid, spec.parent_uid,
                expected_egress_ip=spec.egress_ip if bound else None).validate(context, identity, require_ip=bound)
            if (identity.authorities != spec.authorities
                    or bound and identity.ip_whitelist != (spec.egress_ip,)
                    or not bound and identity.ip_whitelist not in (None, ())):
                raise DemoRejected("native_start_identity_changed")
            wallet, positions = get("wallet"), get("positions")
            result = native_start_account(wallet, positions, binding, context=context, now_ms=self.now())
            check()
            return result
        finally:
            self.lock.release()
