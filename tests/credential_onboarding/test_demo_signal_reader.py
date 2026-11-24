"""Original read audience/current actor and metadata, no credential decrypt."""
import json
import unittest
from unittest.mock import patch

import test_demo_account_sync as account_fixture
from investalo_credential_store.request_assertion import OnboardingRejected
from investalo_credential_store.demo_trading_runtime import _application_executor


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
