"""Original read audience/current actor and metadata, no credential decrypt."""
import json
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

import test_demo_account_sync as account_fixture
from investalo_credential_store.request_assertion import OnboardingRejected
from investalo_credential_store.demo_trading_runtime import _application_executor
from investalo_credential_store.private_http import (
    DemoTradingAccountHTTPApplication, DemoMarketTestHTTPApplication, _application_result,
)


def signal_view():
    from investalo_bitget.futures_demo_signals import SYMBOLS
    now = datetime.now(timezone.utc)
    end = now.replace(minute=0, second=0, microsecond=0)
    return dict(schema="investalo-demo-signals/1", tenant_id=str(UUID(int=1)),
        account_id=str(UUID(int=3)), source="bitget_classic_demo", execution_enabled=False,
        observed_at=now.isoformat(), timeframe="H1", rsi_period=14, warmup_bars=300,
        next_candle_close=(end+timedelta(hours=1)).isoformat(), assets=[
            dict(symbol=symbol, status="confirmed", rsi="29.9999999999999999999999999999999999",
                previous_rsi="29.5", below_count=2, close_price="60000",
                candle_closed_at=end.isoformat(), fetched_at=now.isoformat(),
                entry_condition="confirmed") for symbol in SYMBOLS])


class DemoSignalReaderTests(unittest.TestCase):
    def setUp(self):
        self.f = account_fixture.DemoAccountTests()
        self.f.setUp()
        self.f.target["inspection"] = "signals"
        self.f.body = json.dumps(self.f.target).encode()
        self.calls = []
        def monitor():
            self.calls.append(True)
            return dict(observed_at="2026-11-24T13:01:00+00:00", timeframe="H1",
                rsi_period=14, warmup_bars=300, next_candle_close="2026-11-24T14:00:00+00:00", assets=[])
        self.f.reader.signal_monitor = monitor

    def test_original_current_read_uses_no_broker_key_or_account_mutex(self):
        self.f.native.lock.acquire()
        try:
            with patch("investalo_credential_store.demo_trading_provider.SealedDemoTradingProvider.__call__",
                       side_effect=AssertionError("no decrypt")):
                result = self.f.run_read()
        finally:
            self.f.native.lock.release()
        self.assertEqual(result["source"], "bitget_classic_demo")
        self.assertIs(result["execution_enabled"], False)
        self.assertEqual(self.f.sent, [])
        self.assertEqual(len(self.calls), 1)

    def test_current_actor_revoked_before_or_during_public_read_rejects(self):
        self.f.revoked = True
        with self.assertRaises(OnboardingRejected): self.f.run_read()
        self.assertEqual(self.calls, [])
        self.f.revoked = False
        self.f.reader.signal_monitor = lambda: setattr(self.f, "revoked", True) or {}
        with self.assertRaises(OnboardingRejected): self.f.run_read()
        self.assertEqual(self.f.sent, [])

    def test_foreign_revision_and_wrong_audience_do_not_read_market(self):
        for change in (dict(kind="investalo-demo-btc-market-consent/1"),
                       dict(aud="investalo-demo-btc-market"), dict(auth_epoch=4)):
            with self.assertRaises(OnboardingRejected): self.f.run_read(**change)
        self.f.target["storage_version"] = 2
        self.f.body = json.dumps(self.f.target).encode()
        with self.assertRaises(OnboardingRejected): self.f.run_read()
        self.assertEqual(self.calls, [])

    def test_actual_launcher_forwards_original_signal_read(self):
        expected = {"source": "synthetic public source", "execution_enabled": False}
        calls = []
        def reader(context, token, body):
            calls.append((context, token, body))
            return expected
        execute = _application_executor(self.f.config, self.f.reader.context,
            connect=None, verifier=None, provision=None, keyring=None, guard=lambda: None,
            account_read=reader, market_test=None)
        self.assertIs(execute(self.f.context, "account_read", "original", self.f.body), expected)
        self.assertEqual(calls, [(self.f.context, "original", self.f.body)])

    def test_installed_read_and_market_applications_publish_signal_schema(self):
        for cls in (DemoTradingAccountHTTPApplication, DemoMarketTestHTTPApplication):
            app = cls(self.f.reader.context, lambda *_: None, enabled=True)
            view = signal_view()
            self.assertIs(_application_result(app, view, "account_read"), view)

    def test_signal_projection_rejects_private_foreign_and_invalid_market_fields(self):
        app = DemoMarketTestHTTPApplication(self.f.reader.context, lambda *_: None, enabled=True)
        cases = [
            lambda v: v.update(broker_uid="private"),
            lambda v: v.update(execution_enabled=True),
            lambda v: v.update(source="paper"),
            lambda v: v.update(tenant_id="invalid"),
            lambda v: v["assets"][0].update(envelope="private"),
            lambda v: v["assets"].pop(),
            lambda v: v["assets"].__setitem__(1, deepcopy(v["assets"][0])),
            lambda v: v["assets"][0].update(rsi="100.0000000000000000000000000000000001"),
            lambda v: v["assets"][0].update(rsi="-0"),
            lambda v: v["assets"][0].update(rsi="3e1"),
            lambda v: v["assets"][0].update(below_count=True),
            lambda v: v["assets"][0].update(below_count=1),
            lambda v: v["assets"][0].update(entry_condition="waiting_rsi"),
            lambda v: v["assets"][0].update(close_price="0"),
            lambda v: v["assets"][0].update(candle_closed_at=v["next_candle_close"]),
            lambda v: v["assets"][0].update(fetched_at=v["next_candle_close"]),
            lambda v: v["assets"][0].update(fetched_at="2020-01-01T00:00:00+00:00"),
            lambda v: v.update(next_candle_close=v["observed_at"]),
            lambda v: v.update(observed_at=v["observed_at"].replace("+00:00", "+01:00")),
        ]
        for mutate in cases:
            value = signal_view()
            mutate(value)
            with self.subTest(value=cases.index(mutate)), self.assertRaises(Exception):
                _application_result(app, value, "account_read")

    def test_unknown_and_exact_rsi_thresholds_survive_response_projection(self):
        app = DemoMarketTestHTTPApplication(self.f.reader.context, lambda *_: None, enabled=True)
        from investalo_bitget.futures_demo_signals import unavailable_asset
        for rsi, previous, count, condition in (
                ("30", "29.5", 0, "waiting_rsi"),
                ("30.0000000000000000000000000000000001", "29.5", 0, "waiting_rsi"),
                ("29.5", "30", 1, "waiting_confirmation"),
                ("0", "0", 2, "confirmed"),
                ("100", "100", 0, "waiting_rsi")):
            value = signal_view()
            value["assets"][0].update(rsi=rsi, previous_rsi=previous, below_count=count,
                entry_condition=condition)
            value["assets"][1] = unavailable_asset(value["assets"][1]["symbol"])
            self.assertEqual(_application_result(app, value, "account_read"), value)
            value["assets"][1]["rsi"] = "0"
            with self.assertRaises(Exception):
                _application_result(app, value, "account_read")
