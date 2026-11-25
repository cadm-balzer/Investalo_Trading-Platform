"""Real signed intent/files/journal/AEAD/dispatcher; synthetic actor/native ports."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from investalo_bitget.futures_demo import DemoRejected, digest
from investalo_bitget.futures_demo_basket import BasketMarketGrid, BasketMarketIntent, BasketExitIntent
from investalo_credential_store.demo_worker_authorization import (
    DurableBasketConsumer, verify_worker_intent,
)
from investalo_credential_store.demo_basket_orders import EXIT_PURPOSE
from investalo_trading.futures_broker_journal import BrokerEntryJournal
import test_demo_basket_orders as orders
import test_demo_basket_exits as exits
from test_demo_basket_orders import D, BINDING, OWNER, OTHER

KEY = b"synthetic-worker-intent-key-0000"


def wire(now, *, action="start", revision=1, limit=3, assets=None, binding=BINDING, **changes):
    p = dict(schema="investalo-demo-h1-intent/1", binding=dict(
        tenant_id=str(binding.owner.tenant_id), account_id=str(binding.account_id),
        user_id=str(binding.owner.user_id), subject="synthetic-subject", auth_epoch=0,
        connection_id=str(binding.credential_ref), credential_revision=1, storage_version=1),
        revision=revision, action=action, basket_limit=limit,
        assets=assets or ["BNBUSDT", "BTCUSDT", "ETHUSDT"],
        requested_at=datetime.fromtimestamp(now/1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        **changes)
    payload = json.dumps(p, separators=(",", ":"))
    return json.dumps(dict(payload=payload, mac=hmac.new(KEY, payload.encode(), hashlib.sha256).hexdigest())).encode()


class WorkerAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.f = orders.BasketNativeTests()
        self.f.setUp()
        self.root = Path(self.f.temp.name)/"consumer"
        self.root.mkdir(mode=0o700)
        self.control = wire(self.f.now)
        self.events = []
        self.revoked = False
        self.consumer = self.create()

    def create(self):
        def guard(intent):
            self.events.append("actor")
            if self.revoked or intent.auth_epoch != 0:
                raise DemoRejected("actor_changed")
        return DurableBasketConsumer(self.root, binding=BINDING, intent_key=KEY,
            read_control=lambda: self.control, actor_guard=guard, journal=self.f.journal,
            milliseconds=lambda: self.f.now)

    def tearDown(self):
        self.consumer.close()
        self.f.tearDown()

    def intent(self):
        order = self.f.journal.state.book.pending
        grid = BasketMarketGrid("BTCUSDT", D(".0001"), D(".1"), D(".0001"), D(5), D(10))
        return BasketMarketIntent(BINDING, self.f.journal_id if hasattr(self.f, "journal_id")
            else __import__("uuid").UUID(self.f.journal._header["journal_id"]),
            order.command_id, order.order_digest, grid, order.assessment.capital.stage, order.cycle,
            order.request.quantity, order.request.maximum_fill_price, order.request.posted_margin,
            order.before_quantity, order.before_average, self.f.now)

    def authorize(self):
        return self.consumer(self.intent(), self.f.journal.receipt, OWNER)

    def test_original_wire_never_renews_auth_time_and_rejects_foreign_bad_mac_unknown_duplicate(self):
        first = self.consumer.sync()
        self.f.now += 100000
        self.assertEqual(self.consumer.sync().requested_ms, first.requested_ms)
        for raw in (self.control.replace(b'"mac": "', b'"mac": "a'),
                    self.control.replace(b'"payload":', b'"extra":null,"payload":'),
                    self.control.replace(b'"payload":', b'"mac":"x","payload":'),
                    wire(self.f.now, revision=True), wire(self.f.now, assets=["BTCUSDT", "BTCUSDT"]),
                    wire(self.f.now, assets=["ETHUSDT", "BTCUSDT"])):
            with self.subTest(raw=raw[:20]), self.assertRaises(DemoRejected):
                verify_worker_intent(raw, KEY, binding=BINDING, now_ms=self.f.now)
        with self.assertRaises(DemoRejected):
            verify_worker_intent(self.control, b"x"*32, binding=BINDING, now_ms=self.f.now)

    def test_once_actual_dispatch_consumes_before_secret_and_never_resends_after_restore(self):
        dispatcher = self.f.dispatcher(authorize_once=self.consumer)
        self.assertEqual(dispatcher.dispatch(context=OWNER, expected_revision=self.f.journal.state.revision), "acknowledged")
        spent = list(self.root.glob("consumed-*"))
        self.assertEqual(len(spent), 1)
        self.assertEqual(json.loads(json.loads(spent[0].read_text())["payload"])["purpose"],
                         "bitget-demo-h1-basket-entry/1")
        self.assertEqual(len(self.f.sent), 1)
        self.consumer.close()
        self.consumer = self.create()
        with self.assertRaises(DemoRejected):
            dispatcher.dispatch(context=OWNER, expected_revision=self.f.journal.state.revision)
        self.assertEqual(len(self.f.sent), 1)

    def test_consumption_without_dispatch_is_spent_across_restart(self):
        self.authorize()
        self.consumer.close()
        self.consumer = self.create()
        with self.assertRaisesRegex(DemoRejected, "already_consumed"):
            self.authorize()
        self.assertEqual(self.f.sent, [])

    def test_pause_and_rollback_rejected_after_restart_then_fresh_start_accepted(self):
        self.consumer.sync()
        original = self.control
        self.control = wire(self.f.now, action="pause", revision=2)
        self.assertEqual(self.consumer.sync().action, "pause")
        with self.assertRaisesRegex(DemoRejected, "paused"):
            self.authorize()
        self.consumer.close()
        self.consumer = self.create()
        self.control = original
        with self.assertRaisesRegex(DemoRejected, "rollback"):
            self.consumer.sync()
        self.control = wire(self.f.now, revision=2)
        with self.assertRaisesRegex(DemoRejected, "revision_reuse"):
            self.consumer.sync()
        self.control = wire(self.f.now, revision=3)
        self.authorize()

    def test_settings_revocation_foreign_context_changed_receipt_cannot_consume(self):
        for control in (wire(self.f.now, assets=["ETHUSDT"]),
                        wire(self.f.now, limit=4)):
            self.control = control
            with self.assertRaises(DemoRejected):
                self.authorize()
            self.consumer.close()
            # Reset only this synthetic test installation, never runtime.
            for p in self.root.iterdir():
                if p.name != "lock":
                    p.unlink()
            self.consumer = self.create()
        self.control = wire(self.f.now)
        self.revoked = True
        with self.assertRaises(DemoRejected):
            self.authorize()
        self.revoked = False
        with self.assertRaises(DemoRejected):
            self.consumer(self.intent(), self.f.journal.receipt, OTHER)
        with self.assertRaises(DemoRejected):
            self.consumer(self.intent(), {**self.f.journal.receipt, "head": "a"*64}, OWNER)
        self.assertEqual(list(self.root.glob("consumed-*")), [])

    def test_forged_stage_and_exit_for_same_command_digest_do_not_gain_approval(self):
        original = self.intent()
        fake_exit = BasketExitIntent(original.binding, original.journal_id, original.command_id,
            original.order_digest, original.grid, original.cycle, original.quantity,
            original.planning_price, original.quantity, original.planning_price, original.prepared_ms)
        for intent in (replace(original, stage=2), fake_exit):
            with self.assertRaisesRegex(DemoRejected, "differs_from_original"):
                self.consumer(intent, self.f.journal.receipt, OWNER)
        self.assertEqual(list(self.root.glob("consumed-*")), [])

    def test_pause_during_actual_spend_keeps_command_spent_and_denies_post(self):
        original = self.consumer._write
        def changed(name, raw, **options):
            original(name, raw, **options)
            if name.startswith("consumed-"):
                self.control = wire(self.f.now, action="pause", revision=2)
        with patch.object(self.consumer, "_write", changed):
            with self.assertRaisesRegex(DemoRejected, "changed_during"):
                self.authorize()
        self.assertEqual(len(list(self.root.glob("consumed-*"))), 1)
        self.assertEqual(self.f.sent, [])

    def test_uncertain_fsync_partial_spend_never_removed_or_retried(self):
        self.consumer.sync()
        with patch("os.fsync", side_effect=OSError("synthetic lost ACK")):
            with self.assertRaisesRegex(DemoRejected, "write_unconfirmed"):
                self.authorize()
        self.assertEqual(len(list(self.root.glob("consumed-*"))), 1)
        self.consumer.close()
        self.consumer = self.create()
        with self.assertRaisesRegex(DemoRejected, "already_consumed"):
            self.authorize()

    def test_original_inode_fork_and_second_worker_fail_closed(self):
        second = self.create()
        try:
            self.consumer.sync()
            second.sync()
            with self.consumer._locked():
                with self.assertRaisesRegex(DemoRejected, "busy"):
                    second.sync()
        finally:
            second.close()
        with patch("os.getpid", return_value=os.getpid()+1):
            with self.assertRaises(DemoRejected):
                self.consumer.sync()
        self.root.rename(self.root.with_name("old-consumer"))
        self.root.mkdir(mode=0o700)
        with self.assertRaisesRegex(DemoRejected, "root_replaced"):
            self.consumer.sync()

    def test_missing_checkpoint_after_spend_and_symlink_checkpoint_do_not_rearm(self):
        self.authorize()
        (self.root/"state").unlink()
        with self.assertRaisesRegex(DemoRejected, "checkpoint_missing"):
            self.consumer.sync()
        (self.root/"state").symlink_to(self.root/next(p.name for p in self.root.glob("consumed-*")))
        with self.assertRaises((DemoRejected, OSError)):
            self.consumer.sync()

    def test_pause_checkpoint_loss_without_orders_cannot_rearm_old_start(self):
        self.consumer.sync()
        old_start = self.control
        self.control = wire(self.f.now, action="pause", revision=2)
        self.consumer.sync()
        (self.root/"state").unlink()
        self.control = old_start
        with self.assertRaisesRegex(DemoRejected, "checkpoint_missing"):
            self.consumer.sync()

    def test_owned_native_reduce_only_exit_remains_authorized_after_pause(self):
        self.consumer.close()
        self.f.tearDown()
        e = exits.NativeExitTests()
        e.setUp()
        self.f = e.f
        # Use the existing actual owned-position/full-exit journal fixture.
        self.root = Path(self.f.temp.name)/"consumer"
        self.root.mkdir(mode=0o700)
        self.control = wire(self.f.now)
        self.consumer = self.create()
        self.consumer.sync()
        self.control = wire(self.f.now, action="pause", revision=2, assets=["ETHUSDT"])
        dispatcher = self.f.dispatcher(read_transport=e.native, order_transport=e.send,
            margin_resolver=None, margin_source=e.source, authorize_once=self.consumer)
        self.assertEqual(dispatcher.dispatch(context=OWNER, expected_revision=self.f.journal.state.revision), "acknowledged")
        self.assertEqual(len(e.posts), 1)
        record = json.loads(json.loads(next(self.root.glob("consumed-*")).read_text())["payload"])
        self.assertEqual(record["purpose"], EXIT_PURPOSE)
        self.assertEqual(json.loads(e.posts[0].body)["reduceOnly"], "YES")
