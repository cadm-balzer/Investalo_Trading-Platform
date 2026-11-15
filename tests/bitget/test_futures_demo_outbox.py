"""Real private filesystem/CAS/flock/fault tests; no network or real credentials."""
from dataclasses import replace
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Barrier, Thread
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_bitget import BitgetRejected
from investalo_bitget.futures_demo import DemoRejected, digest
from investalo_bitget.futures_demo_outbox import DemoOutbox, encode, _trace_record
from test_futures_demo import AT, OWNER, OTHER, BINDING, intent, response, detail

BOX = UUID(int=123)


class DemoOutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.box = DemoOutbox.create(self.root, binding=BINDING, outbox_id=BOX, context=OWNER)

    def tearDown(self):
        self.box.close()
        self.tmp.cleanup()

    def restore(self, **kwargs):
        self.box.close()
        self.box = DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX,
                                     context=OWNER, **kwargs)
        return self.box

    def prepare(self, order=None):
        order = order or intent()
        self.box.prepare(order, context=OWNER, expected_revision=self.box.receipt.revision)
        return order

    def dispatch(self, order=None):
        order = self.prepare(order)
        self.box.begin_attempt(order.command_id, context=OWNER,
                               expected_revision=self.box.receipt.revision, at_ms=AT)
        return order

    def observe(self, order, **changes):
        return self.box.accept_observation(order.command_id, response(detail(order, **changes)),
            context=OWNER, expected_revision=self.box.receipt.revision, now_ms=AT + 100)

    def test_owned_private_files_and_non_executable_genesis(self):
        for name in ("commands.jsonl", "receipt.json", "writer.lock"):
            info = (self.root / name).stat()
            self.assertEqual(info.st_mode & 0o777, 0o600)
            self.assertEqual(info.st_nlink, 1)
            self.assertEqual(info.st_uid, os.geteuid())
        header = json.loads((self.root / "commands.jsonl").read_bytes().splitlines()[0])
        self.assertIs(header["execution_enabled"], False)
        self.assertEqual(self.box.receipt.revision, 0)
        self.assertEqual(self.restore().receipt.revision, 0)

    def test_prepare_roundtrip_stable_bytes_idempotent_and_conflicting_payload(self):
        order = self.prepare()
        receipt, original = self.box.receipt, (self.root / "commands.jsonl").read_bytes()
        self.restore(minimum_receipt=receipt)
        self.assertEqual(self.box.traces(context=OWNER)[0].intent, order)
        self.assertEqual(self.box.prepare(order, context=OWNER, expected_revision=1), receipt)
        self.assertEqual((self.root / "commands.jsonl").read_bytes(), original)
        with self.assertRaisesRegex(DemoRejected, "payload_conflict"):
            self.box.prepare(intent(quantity=Decimal("0.011")), context=OWNER, expected_revision=1)
        self.assertEqual(self.box.receipt, receipt)

    def test_restart_before_attempt_keeps_prepared_order(self):
        self.prepare()
        self.restore()
        self.assertTrue(self.box.traces(context=OWNER)[0].can_submit)

    def test_restart_after_attempt_keeps_unknown_without_resend(self):
        order = self.dispatch()
        receipt = self.box.receipt
        self.restore(minimum_receipt=receipt)
        trace = self.box.traces(context=OWNER)[0]
        self.assertEqual(trace.state, "submission_unknown")
        self.assertFalse(trace.can_submit)
        with self.assertRaisesRegex(DemoRejected, "resend_denied"):
            self.box.begin_attempt(order.command_id, context=OWNER, expected_revision=2, at_ms=AT + 1)
        self.assertEqual(self.box.receipt, receipt)

    def test_missing_ack_id_and_partial_cancellation_restore_exactly(self):
        order = self.dispatch()
        self.box.accept_ack(order.command_id, response({"clientOid": order.client_oid}),
                            context=OWNER, expected_revision=2, now_ms=AT + 100)
        self.observe(order)
        self.observe(order, state="canceled", uTime=str(AT + 30), fee="-0.08")
        before, receipt = self.box.traces(context=OWNER), self.box.receipt
        self.restore(minimum_receipt=receipt)
        self.assertEqual(self.box.traces(context=OWNER), before)
        trace = before[0]
        self.assertEqual(trace.observation.quantity, Decimal("0.004"))
        self.assertEqual(trace.state, "canceled")
        self.assertEqual(trace.observation.reported_fee, Decimal("-0.08"))
        self.box.prepare(order, context=OWNER, expected_revision=5)
        self.assertEqual(self.box.receipt, receipt)  # prepare does not reset terminal history

    def test_full_fill_and_unknown_fee_are_not_a_capital_or_stage_ledger(self):
        order = self.dispatch()
        self.observe(order, state="filled", baseVolume="0.010")
        self.restore()
        trace = self.box.traces(context=OWNER)[0]
        self.assertEqual(trace.observation.quantity, order.quantity)
        self.assertIsNone(trace.observation.reported_fee)
        self.assertFalse(hasattr(self.box, "cash"))
        self.assertFalse(hasattr(trace.observation, "fill_id"))

    def test_stale_cas_and_foreign_user_account_or_key_leave_bytes_unchanged(self):
        order = self.prepare()
        original = (self.root / "commands.jsonl").read_bytes()
        for context, revision in ((OTHER, 1), (OWNER, 0), (OWNER, True)):
            with self.subTest(context=context, revision=revision), self.assertRaises(DemoRejected):
                self.box.begin_attempt(order.command_id, context=context,
                                       expected_revision=revision, at_ms=AT)
        for binding in (replace(BINDING, account_id=UUID(int=999)),
                        replace(BINDING, credential_ref=UUID(int=999))):
            with self.subTest(binding=binding), self.assertRaises(DemoRejected):
                self.box.prepare(intent(binding=binding), context=OWNER, expected_revision=1)
        self.assertEqual((self.root / "commands.jsonl").read_bytes(), original)
        self.assertEqual(self.box.receipt.revision, 1)

    def test_second_actual_writer_rejected_then_release_allows_restore(self):
        with self.assertRaisesRegex(DemoRejected, "writer_busy"):
            DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX, context=OWNER)
        self.prepare()
        self.assertEqual(self.restore().receipt.revision, 1)

    def test_concurrent_same_revision_has_one_committed_winner(self):
        barrier, results = Barrier(3), []

        def prepare(identifier):
            barrier.wait()
            try:
                self.box.prepare(intent(command_id=UUID(int=identifier)), context=OWNER, expected_revision=0)
                results.append("committed")
            except DemoRejected:
                results.append("conflict")
        threads = [Thread(target=prepare, args=(identifier,)) for identifier in (6, 7)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertCountEqual(results, ["committed", "conflict"])
        self.assertEqual(self.box.receipt.revision, 1)

    def test_invalid_broker_response_does_not_mutate_unknown_or_store_provider_msg(self):
        order = self.dispatch()
        before = (self.root / "commands.jsonl").read_bytes()
        for packet in (response(None, code="43025", msg="do-not-store-provider-message"),
                       response(detail(order, baseVolume="0.02")),
                       response(detail(order, clientOid="foreign"))):
            with self.subTest(packet=packet), self.assertRaises((DemoRejected, BitgetRejected)):
                self.box.accept_observation(order.command_id, packet, context=OWNER,
                                             expected_revision=2, now_ms=AT + 100)
        self.assertEqual((self.root / "commands.jsonl").read_bytes(), before)
        self.assertEqual(self.box.traces(context=OWNER)[0].state, "submission_unknown")
        self.box.accept_ack(order.command_id, response({"clientOid": order.client_oid}, msg="not-an-archive"),
                            context=OWNER, expected_revision=2, now_ms=AT + 100)
        self.assertNotIn(b"not-an-archive", (self.root / "commands.jsonl").read_bytes())

    def test_unknown_checkpoint_write_keeps_full_dispatch_suffix_on_restore(self):
        order = self.prepare()
        minimum = self.box.receipt
        with patch.object(self.box, "_publish", side_effect=OSError("synthetic failure")):
            with self.assertRaisesRegex(DemoRejected, "write_unknown"):
                self.box.begin_attempt(order.command_id, context=OWNER, expected_revision=1, at_ms=AT)
        with self.assertRaisesRegex(DemoRejected, "stopped"):
            self.box.prepare(intent(command_id=UUID(int=7)), context=OWNER, expected_revision=1)
        self.restore(minimum_receipt=minimum)
        self.assertEqual(self.box.receipt.revision, 2)
        self.assertFalse(self.box.traces(context=OWNER)[0].can_submit)
        self.assertEqual(json.loads((self.root / "receipt.json").read_bytes()), self.box.receipt.record())

    def test_unknown_readback_after_checkpoint_rename_restores_ack_without_fill(self):
        order = self.dispatch()
        read = self.box._read_checkpoint
        calls = 0

        def fail_after_publish():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic readback failure")
            return read()
        with patch.object(self.box, "_read_checkpoint", side_effect=fail_after_publish):
            with self.assertRaisesRegex(DemoRejected, "write_unknown"):
                self.box.accept_ack(order.command_id, response({"clientOid": order.client_oid, "orderId": "123"}),
                                    context=OWNER, expected_revision=2, now_ms=AT + 100)
        self.restore()
        trace = self.box.traces(context=OWNER)[0]
        self.assertEqual(trace.state, "acknowledged")
        self.assertEqual(trace.order_id, "123")
        self.assertIsNone(trace.observation)
        self.assertFalse(trace.can_submit)

    def test_actual_process_exit_after_durable_attempt_never_rearms_send(self):
        self.prepare()
        self.box.close()
        script = """
import os, sys
from test_futures_demo import AT, OWNER, BINDING, intent
from investalo_bitget.futures_demo_outbox import DemoOutbox
from uuid import UUID
box = DemoOutbox.restore(sys.argv[1], binding=BINDING, outbox_id=UUID(int=123), context=OWNER)
box.begin_attempt(intent().command_id, context=OWNER, expected_revision=1, at_ms=AT)
os._exit(23)
"""
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                           PYTHONPATH="integrations/bitget/src:tests/bitget")
        child = subprocess.run([sys.executable, "-c", script, str(self.root)],
                               env=environment, capture_output=True, timeout=5)
        self.assertEqual(child.returncode, 23, child.stderr.decode())
        self.restore()
        self.assertEqual(self.box.receipt.revision, 2)
        self.assertFalse(self.box.traces(context=OWNER)[0].can_submit)

    def test_fsync_failure_stops_writer_and_full_valid_attempt_is_restored(self):
        order = self.prepare()
        with patch("investalo_bitget.futures_demo_outbox.os.fsync", side_effect=OSError("synthetic")):
            with self.assertRaisesRegex(DemoRejected, "write_unknown"):
                self.box.begin_attempt(order.command_id, context=OWNER, expected_revision=1, at_ms=AT)
        with self.assertRaises(DemoRejected):
            _ = self.box.receipt
        self.restore()
        self.assertEqual(self.box.traces(context=OWNER)[0].state, "submission_unknown")

    def test_partial_append_never_gets_repaired_or_resent(self):
        order = self.prepare()

        def partial(data):
            os.write(self.box._journal_fd, data[:20])
            raise OSError("synthetic partial append")
        with patch.object(self.box, "_append_bytes", side_effect=partial):
            with self.assertRaisesRegex(DemoRejected, "write_unknown"):
                self.box.begin_attempt(order.command_id, context=OWNER, expected_revision=1, at_ms=AT)
        evidence = (self.root / "commands.jsonl").read_bytes()
        self.box.close()
        with self.assertRaisesRegex(DemoRejected, "incomplete_journal"):
            DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX, context=OWNER)
        self.assertEqual((self.root / "commands.jsonl").read_bytes(), evidence)

    def test_truncation_below_private_checkpoint_and_explicit_minimum_reject(self):
        self.dispatch()
        minimum = self.box.receipt
        self.box.close()
        lines = (self.root / "commands.jsonl").read_bytes().splitlines(keepends=True)
        (self.root / "commands.jsonl").write_bytes(b"".join(lines[:-1]))
        with self.assertRaisesRegex(DemoRejected, "below_minimum"):
            DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX, context=OWNER)
        # Even if an older private checkpoint is supplied, caller's trusted receipt anchors the floor.
        header = json.loads(lines[0])
        state = digest({"binding": BINDING.record(), "traces": []})
        old = replace(minimum, revision=0, head=digest(header), state_digest=state)
        (self.root / "receipt.json").write_bytes(encode(old.record()))
        with self.assertRaisesRegex(DemoRejected, "below_minimum"):
            DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX, context=OWNER,
                               minimum_receipt=minimum)

    def test_fork_and_duplicate_record_reject_before_checkpoint_repair(self):
        self.dispatch()
        forked_trace = replace(self.box.traces(context=OWNER)[0], dispatch_ms=AT + 1)
        self.box.close()
        path = self.root / "commands.jsonl"
        original = path.read_bytes()
        lines = original.splitlines(keepends=True)
        damaged = json.loads(lines[-1])
        damaged["head"] = "f" * 64
        forked = json.loads(lines[-1])
        forked["command"]["payload"]["at_ms"] = AT + 1
        forked["state_digest"] = digest({"binding": BINDING.record(),
                                        "traces": [_trace_record(forked_trace)]})
        forked["head"] = digest({k: v for k, v in forked.items() if k != "head"})
        for data in (b"".join(lines[:-1]) + encode(damaged) + b"\n", original + lines[-1],
                     b"".join(lines[:-1]) + encode(forked) + b"\n"):
            path.write_bytes(data)
            with self.assertRaises(DemoRejected):
                DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX, context=OWNER)

    def test_foreign_genesis_and_foreign_minimum_reject(self):
        receipt = self.box.receipt
        self.box.close()
        for binding, box_id in ((replace(BINDING, broker_uid="999"), BOX),
                                (BINDING, UUID(int=999))):
            with self.subTest(binding=binding, box_id=box_id), self.assertRaises(DemoRejected):
                DemoOutbox.restore(self.root, binding=binding, outbox_id=box_id, context=OWNER)
        with self.assertRaises(DemoRejected):
            DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX, context=OWNER,
                               minimum_receipt=replace(receipt, binding_digest="f" * 64))

    def test_reinitialization_rejected_without_resetting_original(self):
        self.dispatch()
        original = (self.root / "commands.jsonl").read_bytes()
        self.box.close()
        with self.assertRaises(DemoRejected):
            DemoOutbox.create(self.root, binding=BINDING, outbox_id=BOX, context=OWNER)
        self.assertEqual((self.root / "commands.jsonl").read_bytes(), original)

    def test_private_permissions_symlinks_and_hardlinks_reject(self):
        self.box.close()
        path = self.root / "commands.jsonl"
        path.chmod(0o644)
        with self.assertRaises(DemoRejected):
            DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX, context=OWNER)
        path.chmod(0o600)
        alias = self.root / "alias"
        os.link(path, alias)
        with self.assertRaises(DemoRejected):
            DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX, context=OWNER)
        alias.unlink()
        moved = self.root / "original"
        path.rename(moved)
        path.symlink_to(moved)
        with self.assertRaises((DemoRejected, OSError)):
            DemoOutbox.restore(self.root, binding=BINDING, outbox_id=BOX, context=OWNER)
        with tempfile.TemporaryDirectory() as parent:
            alias = Path(parent) / "alias"
            alias.symlink_to(self.root, target_is_directory=True)
            with self.assertRaises((DemoRejected, OSError)):
                DemoOutbox.restore(alias, binding=BINDING, outbox_id=BOX, context=OWNER)

    def test_external_journal_or_checkpoint_drift_stops_active_writer(self):
        order = self.prepare()
        (self.root / "receipt.json").write_bytes(b"{}")
        with self.assertRaisesRegex(DemoRejected, "write_unknown"):
            self.box.begin_attempt(order.command_id, context=OWNER, expected_revision=1, at_ms=AT)

        self.box.close()
        with tempfile.TemporaryDirectory() as root:
            with DemoOutbox.create(root, binding=BINDING, outbox_id=BOX, context=OWNER) as box:
                box.prepare(intent(), context=OWNER, expected_revision=0)
                (Path(root) / "writer.lock").rename(Path(root) / "original.lock")
                replacement = Path(root) / "writer.lock"
                replacement.touch(mode=0o600)
                with self.assertRaisesRegex(DemoRejected, "write_unknown"):
                    box.begin_attempt(intent().command_id, context=OWNER, expected_revision=1, at_ms=AT)
        with self.assertRaisesRegex(DemoRejected, "stopped"):
            self.box.begin_attempt(order.command_id, context=OWNER, expected_revision=1, at_ms=AT)

    def test_capacity_is_bounded_and_failed_validation_does_not_poison(self):
        self.box.close()
        with tempfile.TemporaryDirectory() as root:
            with DemoOutbox.create(root, binding=BINDING, outbox_id=BOX, context=OWNER, capacity=1) as box:
                box.prepare(intent(), context=OWNER, expected_revision=0)
                with self.assertRaisesRegex(DemoRejected, "capacity_exhausted"):
                    box.begin_attempt(intent().command_id, context=OWNER, expected_revision=1, at_ms=AT)
                self.assertEqual(box.receipt.revision, 1)
                self.assertTrue(box.traces(context=OWNER)[0].can_submit)


if __name__ == "__main__":
    unittest.main()
