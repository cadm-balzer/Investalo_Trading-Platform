"""Invented bounded account cohorts plus the actual private outbox path."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from uuid import UUID

from investalo_bitget import BitgetRejected
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_account import (
    AXES, CONFIGS, AccountExpectation, DemoReadPlan, DemoPacket, check_account,
)
from investalo_bitget.futures_demo_outbox import DemoOutbox
from test_futures_demo import AT, BINDING, OWNER, OTHER, intent, response, detail, positions

D = Decimal


def expectation(**changes):
    initial = tuple((s, D("0.020") if s == "BTCUSDT" else D(0)) for s in CONFIGS)
    return AccountExpectation(**{"binding": BINDING, "initial_positions": initial,
        "expected_available": D("10000"), "reserved_cash": D("8000"), **changes})


def wallet(**changes):
    return [{"marginCoin": "USDT", "assetMode": "single", "available": "10000",
             "locked": "0", "accountEquity": "10001", "unrealizedPL": "1",
             "isolatedMargin": "500", "crossedMargin": "0", "coupon": "0", "grant": "0", **changes}]


def config(**changes):
    return {"marginCoin": "USDT", "assetMode": "single", "marginMode": "isolated",
            "posMode": "one_way_mode", "isolatedLongLever": "2", **changes}


def cohort():
    packets = []
    for axis in (*AXES, *CONFIGS):
        raw = (wallet() if axis == "wallet" else positions("0.020") if axis == "positions"
               else config() if axis in CONFIGS else {"entrustedList": [], "endId": ""})
        packets.append(DemoPacket(DemoReadPlan(BINDING, axis), response(raw)))
    return tuple(packets)


def substitute(packets, axis, raw, *, at=AT + 100):
    return tuple(DemoPacket(p.plan, response(raw, at=at)) if p.plan.axis == axis else p for p in packets)


def pending(order=None, *, identifier="123", state="live", symbol="BTCUSDT"):
    return {"orderId": identifier, "clientOid": order.client_oid if order else "foreign",
            "symbol": symbol, "status": state, "size": "0.010"}


def paged(packets, axis, rows, end_id="123"):
    packets = substitute(packets, axis, {"entrustedList": rows, "endId": end_id})
    if end_id:
        packets += (DemoPacket(DemoReadPlan(BINDING, axis, end_id),
                               response({"entrustedList": [], "endId": ""})),)
    return packets


class AccountReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.box = DemoOutbox.create(self.root, binding=BINDING, outbox_id=UUID(int=99), context=OWNER)

    def tearDown(self):
        self.box.close()
        self.tmp.cleanup()

    def check(self, packets=None, expected=None, *, now=AT + 100):
        return self.box.check_account(expected or expectation(), packets or cohort(),
                    context=OWNER, expected_revision=self.box.receipt.revision, now_ms=now)

    def dispatch(self, order=None, *, at=AT):
        order = order or intent()
        self.box.prepare(order, context=OWNER, expected_revision=self.box.receipt.revision)
        self.box.begin_attempt(order.command_id, context=OWNER,
                               expected_revision=self.box.receipt.revision, at_ms=at)
        return order

    def observe(self, order, **changes):
        self.box.accept_observation(order.command_id, response(detail(order, **changes)),
            context=OWNER, expected_revision=self.box.receipt.revision, now_ms=AT + 100)

    def test_all_fourteen_axes_fixed_gets_without_symbol_filter_on_pending(self):
        plans = [p.plan for p in cohort()]
        self.assertEqual(len(plans), 14)
        for plan in plans:
            self.assertEqual(plan.method, "GET")
            self.assertEqual(dict(plan.headers), {"paptrading": "1"})
            if plan.axis in AXES[2:]:
                self.assertNotIn("symbol=", plan.target)
                self.assertNotIn("startTime=", plan.target)
                self.assertIn("limit=100", plan.target)
        self.assertIn("status=partially_filled", DemoReadPlan(BINDING, "partially_filled").target)
        self.assertIn("planType=profit_loss", DemoReadPlan(BINDING, "profit_loss").target)
        for axis, cursor in (("wallet", "123"), ("BTCUSDT", "123"), ("set-leverage", None)):
            with self.subTest(axis=axis), self.assertRaises(DemoRejected):
                DemoReadPlan(BINDING, axis, cursor)

    def test_matching_snapshot_is_advisory_and_equity_does_not_add_pnl(self):
        before = (self.root / "commands.jsonl").read_bytes()
        result = self.check()
        self.assertTrue(result.matched)
        self.assertEqual(result.account_equity, D("10001"))
        self.assertEqual(result.unrealized_pnl, D(1))
        self.assertFalse(result.execution_ready)
        self.assertFalse(result.cash_ledger_ready)
        self.assertFalse(result.pending_scope_verified)  # page exhaustion is not older-order coverage proof
        self.assertEqual(len(result.source_hashes), 14)
        self.assertEqual((self.root / "commands.jsonl").read_bytes(), before)
        self.assertEqual(self.box.receipt.revision, 0)

    def test_missing_duplicate_foreign_or_stale_axes_fail(self):
        packets = cohort()
        cases = (packets[:-1], packets + (packets[0],),
                 (replace(packets[0], plan=DemoReadPlan(replace(BINDING, account_id=UUID(int=999)), "wallet")),)
                 + packets[1:], substitute(packets, "wallet", wallet(), at=AT - 5000))
        for case in cases:
            with self.subTest(case=len(case)), self.assertRaises(DemoRejected):
                self.check(case)
        with self.assertRaises(DemoRejected):
            self.check(now=AT + 99)

    def test_owner_cas_receipt_and_later_check_freshness_bind_result(self):
        result = self.check()
        result.check_current(BINDING, self.box.receipt, context=OWNER, now_ms=AT + 101)
        with self.assertRaises(DemoRejected):
            self.box.check_account(expectation(), cohort(), context=OTHER, expected_revision=0, now_ms=AT + 100)
        with self.assertRaises(DemoRejected):
            result.check_current(BINDING, self.box.receipt, context=OWNER, now_ms=AT + 5101)
        self.box.prepare(intent(), context=OWNER, expected_revision=0)
        with self.assertRaises(DemoRejected):
            result.check_current(BINDING, self.box.receipt, context=OWNER, now_ms=AT + 100)
        with self.assertRaises(DemoRejected):
            check_account(expectation(), self.box.receipt, (), cohort(), context=OWNER, now_ms=AT + 100)

    def test_all_seven_symbol_modes_and_integer_leverage_checked(self):
        self.assertTrue(self.check(substitute(cohort(), "AVAXUSDT", config(isolatedLongLever=2))).matched)
        for changes in ({"isolatedLongLever": True}, {"isolatedLongLever": "3"},
                        {"marginMode": "crossed"}, {"posMode": "hedge_mode"},
                        {"assetMode": "union"}):
            with self.subTest(changes=changes):
                result = self.check(substitute(cohort(), "LINKUSDT", config(**changes)))
                self.assertIn("unsupported_account_configuration", result.blockers)

    def test_missing_cash_and_native_drift_are_not_replaced_by_paper_balance(self):
        result = self.check(expected=expectation(expected_available=None))
        self.assertIn("cash_expectation_unknown", result.blockers)
        result = self.check(substitute(cohort(), "wallet", wallet(available="9999")))
        self.assertIn("cash_drift", result.blockers)
        result = self.check(substitute(cohort(), "wallet", wallet(available="")))
        self.assertIsNone(result.available)
        self.assertIn("wallet_amounts_unknown", result.blockers)

    def test_negative_native_cash_and_full_declared_reservations_are_retained(self):
        result = self.check(substitute(cohort(), "wallet", wallet(available="-1")),
                            expectation(expected_available=D(-1)))
        self.assertEqual(result.available, D(-1))
        self.assertIn("cash_below_declared_reservations", result.blockers)
        self.assertIn("cash_below_declared_reservations",
                      self.check(expected=expectation(reserved_cash=D("10001"))).blockers)

    def test_cross_collateral_bonus_unknown_values_and_multi_assets_are_blocked(self):
        for changes in ({"crossedMargin": "1"}, {"crossedMargin": None},
                        {"coupon": "1"}, {"grant": ""}, {"assetMode": "union"},
                        {"assetList": [{"coin": "BTC", "balance": "1", "available": "1"}]}):
            with self.subTest(changes=changes):
                result = self.check(substitute(cohort(), "wallet", wallet(**changes)))
                self.assertIn("unsupported_wallet_or_unknown_collateral", result.blockers)

    def test_baseline_requires_all_seven_sorted_own_positions(self):
        base = expectation()
        for initial in (base.initial_positions[:-1], tuple(reversed(base.initial_positions)),
                        (("BTCUSDT", D(0)),) * 7):
            with self.assertRaises(DemoRejected):
                expectation(initial_positions=initial)

    def test_foreign_position_short_and_inconsistent_locked_quantities_fail(self):
        for rows in (positions("0.020", symbol="DOGEUSDT"), positions("0.020", holdSide="short"),
                     positions("0.020", locked="1"), positions("0.020") * 2):
            with self.subTest(rows=rows), self.assertRaises(DemoRejected):
                self.check(substitute(cohort(), "positions", rows))
        self.assertIn("position_drift", self.check(substitute(cohort(), "positions", [])).blockers)

    def test_unknown_attempt_stays_unknown_despite_empty_pending_lists(self):
        self.dispatch()
        self.assertIn("unresolved_order", self.check().blockers)
        self.assertEqual(self.box.traces(context=OWNER)[0].state, "submission_unknown")
        self.assertFalse(self.box.traces(context=OWNER)[0].can_submit)

    def test_partial_then_canceled_keeps_only_actual_filled_position(self):
        order = self.dispatch()
        self.observe(order, state="canceled", fee="-0.08")
        result = self.check(substitute(cohort(), "positions", positions("0.024")))
        self.assertTrue(result.matched)
        self.assertIn("position_drift", self.check(substitute(cohort(), "positions", positions("0.030"))).blockers)

    def test_complete_close_and_peer_candidates_preserve_quantity_history(self):
        order = self.dispatch(intent(action="reduce_long", quantity=D("0.020")))
        self.observe(order, state="filled", baseVolume="0.020", fee="-0.2")
        empty = substitute(substitute(cohort(), "positions", []), "wallet",
                           wallet(isolatedMargin="0", unrealizedPL="0", accountEquity="10000"))
        self.assertTrue(self.check(empty).matched)
        self.assertIn("wallet_exposure_drift", self.check(substitute(cohort(), "positions", [])).blockers)
        self.assertIn("position_drift", self.check(substitute(cohort(), "positions",
                                      positions("1", symbol="SOLUSDT"))).blockers)

    def test_full_fill_with_unknown_fee_cannot_claim_known_costs(self):
        order = self.dispatch()
        self.observe(order, state="filled", baseVolume="0.010")
        result = self.check(substitute(cohort(), "positions", positions("0.030")))
        self.assertIn("order_fees_unknown", result.blockers)
        self.assertFalse(result.cash_ledger_ready)

    def test_snapshots_before_latest_order_evidence_and_sequence_ambiguity_block(self):
        order = self.dispatch()
        self.observe(order, state="canceled", baseVolume="0", priceAvg="", fee="0")
        result = self.check(substitute(cohort(), "wallet", wallet(), at=AT + 99))
        self.assertIn("account_cohort_precedes_order_evidence", result.blockers)
        second = self.dispatch(intent(command_id=UUID(int=7)), at=AT)
        self.observe(second, state="canceled", baseVolume="0", priceAvg="", fee="0")
        self.assertIn("ambiguous_order_sequence", self.check().blockers)

    def test_sequential_ladder_uses_last_actual_fill_and_exact_before_quantity(self):
        first = self.dispatch()
        self.observe(first, state="filled", baseVolume="0.010", fee="-0.2")
        second = self.dispatch(intent(command_id=UUID(int=7), before_quantity=D("0.030")), at=AT + 11)
        self.observe(second, cTime=str(AT + 12), state="canceled", baseVolume="0", priceAvg="", fee="0")
        self.assertTrue(self.check(substitute(cohort(), "positions", positions("0.030"))).matched)

    def test_live_and_partially_filled_are_separate_axes_and_foreign_orders_block(self):
        for axis in ("live", "partially_filled"):
            result = self.check(paged(cohort(), axis, [pending(state=axis)]))
            self.assertEqual(result.foreign_pending, ("123",))
            self.assertIn("foreign_orders_present", result.blockers)
            self.assertIn("normal_orders_present", result.blockers)
            self.assertNotIn("pending_coverage_incomplete", result.blockers)
        manual = {**pending(), "clientOid": None}
        self.assertEqual(self.check(paged(cohort(), "live", [manual])).foreign_pending, ("123",))

    def test_known_pending_order_keeps_own_id_and_detects_term_drift(self):
        order = self.dispatch()
        result = self.check(paged(cohort(), "live", [pending(order)]))
        self.assertEqual(result.own_pending, ("123",))
        self.assertFalse(result.foreign_pending)
        result = self.check(paged(cohort(), "live", [pending(order, symbol="ETHUSDT")]))
        self.assertIn("own_pending_order_drift", result.blockers)

    def test_each_trigger_family_blocks_without_cancelling_anything(self):
        for axis in ("normal_plan", "track_plan", "profit_loss"):
            result = self.check(paged(cohort(), axis, [{"orderId": "123"}]))
            self.assertEqual(result.trigger_count, 1)
            self.assertIn("trigger_orders_present", result.blockers)
            self.assertFalse(result.execution_ready)

    def test_nonempty_short_page_and_missing_cursor_do_not_prove_coverage(self):
        for end_id in ("123", ""):
            result = self.check(substitute(cohort(), "live",
                              {"entrustedList": [pending()], "endId": end_id}))
            self.assertIn("pending_coverage_incomplete", result.blockers)
        with self.assertRaises(DemoRejected):
            self.check(substitute(cohort(), "live", {"entrustedList": []}))

    def test_cursor_omission_repeat_wrong_status_and_duplicate_axes_fail(self):
        base = substitute(cohort(), "live", {"entrustedList": [pending()], "endId": "123"})
        for plan, raw in ((DemoReadPlan(BINDING, "live"), {"entrustedList": [], "endId": ""}),
                          (DemoReadPlan(BINDING, "live", "123"),
                           {"entrustedList": [pending()], "endId": "123"})):
            with self.assertRaises(DemoRejected):
                self.check(base + (DemoPacket(plan, response(raw)),))
        with self.assertRaises(DemoRejected):
            self.check(paged(cohort(), "live", [pending(state="partially_filled")]))
        with self.assertRaises(DemoRejected):
            self.check(paged(paged(cohort(), "live", [pending()]), "partially_filled",
                            [pending(state="partially_filled")]))
        complete = base + (
            DemoPacket(DemoReadPlan(BINDING, "live", "123"),
                       response({"entrustedList": [pending(identifier="100")], "endId": "100"})),
            DemoPacket(DemoReadPlan(BINDING, "live", "100"),
                       response({"entrustedList": [], "endId": ""})),)
        result = self.check(complete)
        self.assertEqual(result.foreign_pending, ("123", "100"))
        self.assertNotIn("pending_coverage_incomplete", result.blockers)

    def test_private_outbox_restore_yields_same_bound_account_check(self):
        order = self.dispatch()
        self.observe(order, state="canceled", fee="-0.08")
        packets = substitute(cohort(), "positions", positions("0.024"))
        result, receipt = self.check(packets), self.box.receipt
        self.box.close()
        self.box = DemoOutbox.restore(self.root, binding=BINDING, outbox_id=UUID(int=99),
                                     context=OWNER, minimum_receipt=receipt)
        self.assertEqual(self.check(packets), result)


if __name__ == "__main__":
    unittest.main()
