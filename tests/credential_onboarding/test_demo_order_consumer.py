"""Real private consume files + dispatcher/AEAD, synthetic consent and native replies."""
from dataclasses import replace
import json
import os
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_bitget.futures_demo import DemoRejected
from investalo_credential_store.demo_order_consumer import DurableDemoOrderConsumer
from investalo_credential_store.demo_order_dispatch import DemoOrderApproval
from investalo_credential_store.demo_trading_provider import SealedDemoTradingProvider
import test_demo_order_dispatch as fixture
from test_futures_demo import OWNER, OTHER


class DurableOrderTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.DemoDispatchTests()
        self.case.setUp()
        self.root = self.case.root / "consents"
        self.root.mkdir(mode=0o700)
        self.reader = self.consumer()

    def tearDown(self):
        self.reader.close()
        self.case.tearDown()

    def consumer(self, **changes):
        return DurableDemoOrderConsumer(self.root, **{
            "issuer": self.case.authorize, "guard": lambda: None,
            "milliseconds": lambda: self.case.now, **changes})

    def consume(self, reader=None):
        return (reader or self.reader)(self.case.order, self.case.box.receipt, OWNER)

    def test_durable_consumption_before_actual_dispatcher_secret_access(self):
        c = self.case
        original = c.provider._read
        def checked(*args):
            self.assertEqual(len(list(self.root.glob("consumed-*.json"))), 1)
            return original(*args)
        c.provider = SealedDemoTradingProvider(c.spec, expected_storage=1,
            read_snapshot=checked, load_keyring=lambda: c.ring,
            expires_ms=c.now+30000, milliseconds=lambda: c.now)
        result = c.dispatch(c.dispatcher(authorize_once=self.reader))
        self.assertEqual(result.outcome, "acknowledged")
        self.assertEqual(len(c.sent), 1)
        markers = list(self.root.glob("consumed-*.json"))
        self.assertEqual(len(markers), 1)
        record = json.loads(markers[0].read_bytes())
        self.assertEqual(record["intent_digest"], c.order.intent_digest)
        self.assertEqual(record["receipt"]["revision"], 1)
        self.assertEqual(os.stat(markers[0]).st_mode & 0o777, 0o600)
        self.assertNotIn("synthetic", markers[0].read_text())

    def test_consumed_grant_stays_spent_after_new_consumer_process(self):
        self.consume()
        self.reader.close()
        self.reader = self.consumer()
        with self.assertRaises(DemoRejected):
            self.consume()

    def test_concurrent_consumers_have_one_winner(self):
        second = self.consumer()
        result = []
        def consume(reader):
            try:
                result.append(self.consume(reader))
            except DemoRejected:
                result.append(None)
        workers = [threading.Thread(target=consume, args=(reader,)) for reader in (self.reader, second)]
        try:
            for worker in workers: worker.start()
            for worker in workers: worker.join()
            self.assertEqual(sum(value is not None for value in result), 1)
        finally:
            second.close()

    def test_missing_consent_changed_price_scope_or_receipt_deny_before_file(self):
        def changed(order, receipt, context):
            return DemoOrderApproval(UUID(int=91),
                replace(order, limit_price=order.limit_price + 1), receipt,
                credential_revision=1, storage_version=1,
                granted_ms=self.case.now, expires_ms=self.case.now+15000)
        for issuer in (lambda *args: None, changed):
            reader = self.consumer(issuer=issuer)
            try:
                with self.assertRaises(DemoRejected):
                    self.consume(reader)
            finally:
                reader.close()
        with self.assertRaises(DemoRejected):
            self.reader(self.case.order, self.case.box.receipt, OTHER)
        with self.assertRaises(DemoRejected):
            self.reader(self.case.order, replace(self.case.box.receipt, binding_digest="0"*64), OWNER)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_expired_consent_or_revoked_actor_stops_before_file(self):
        def expired(order, receipt, context):
            return DemoOrderApproval(UUID(int=91), order, receipt, credential_revision=1,
                storage_version=1, granted_ms=self.case.now-15000, expires_ms=self.case.now)
        for changes in (dict(issuer=expired), dict(guard=lambda: (_ for _ in ()).throw(ValueError()))):
            reader = self.consumer(**changes)
            try:
                with self.assertRaises((DemoRejected, ValueError)):
                    self.consume(reader)
            finally:
                reader.close()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_fsync_failure_retains_marker_and_cannot_be_retried(self):
        with patch("investalo_credential_store.demo_order_consumer.os.fsync", side_effect=OSError):
            with self.assertRaises(OSError):
                self.case.dispatch(self.case.dispatcher(authorize_once=self.reader))
        self.assertEqual(len(list(self.root.iterdir())), 1)
        self.reader.close()
        self.reader = self.consumer()
        with self.assertRaises(DemoRejected):
            self.consume()
        self.assertEqual(self.case.sent, [])
        self.assertEqual(self.case.reads, 0)

    def test_expiry_after_persistence_retains_marker_without_post(self):
        calls = []
        def guard():
            calls.append(True)
            if len(calls) == 3: self.case.now += 15000
        reader = self.consumer(guard=guard)
        try:
            with self.assertRaises(DemoRejected):
                self.consume(reader)
            self.assertEqual(len(list(self.root.iterdir())), 1)
        finally:
            reader.close()

    def test_replaced_root_wrong_permissions_and_fork_are_rejected(self):
        self.root.rename(self.case.root / "original")
        self.root.mkdir(mode=0o700)
        with self.assertRaises(DemoRejected):
            self.consume()
        self.root.chmod(0o755)
        with self.assertRaises(DemoRejected):
            self.consumer()
        self.root.chmod(0o700)
        with patch("investalo_credential_store.demo_order_consumer.os.getpid", return_value=-1):
            with self.assertRaises(DemoRejected):
                self.consume()

    def test_incomplete_marker_from_exited_child_remains_spent(self):
        name = "consumed-" + str(UUID(int=91)) + ".json"
        command = "import os,sys; fd=os.open(sys.argv[1],os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.fsync(fd); os._exit(7)"
        result = subprocess.run([sys.executable, "-c", command, str(self.root / name)],
            env={"PATH": os.environ.get("PATH", "")}, capture_output=True)
        self.assertEqual(result.returncode, 7)
        self.assertEqual((self.root / name).stat().st_size, 0)
        with self.assertRaises(DemoRejected):
            self.consume()
