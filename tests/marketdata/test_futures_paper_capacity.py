"""Actual Paper state/reserves, native eligibility and atomic publication."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import json
from unittest.mock import Mock, patch

from investalo_trading.futures_paper_capacity import (
    PaperInstrumentMinimum, PaperInstrumentEvidence, capacity_state, capacity_snapshot,
)
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader, PaperStatusCommitUnknown
from test_futures_paper_feed import Provider, opened, END
from test_futures_source_worker import configured
from investalo_workers.futures_capacity_source import FuturesPaperCapacitySource
from test_futures_broker_calibration import response


def contracts_payload(state):
    value = response()
    plan = state.config.profile.plan
    for row, contract, grid in zip(value["data"], plan.contracts, plan.grid_rules):
        row.update(volumePlace="4", pricePlace="2", priceEndStep="1",
                   sizeMultiplier=str(contract.quantity_step), minTradeNum=str(contract.minimum_quantity),
                   minTradeUSDT=str(contract.minimum_notional), maxMarketOrderQty=str(grid.maximum_market_quantity))
    return json.dumps(value).encode()


def instruments(state, market=None):
    market = market or Provider(now=state.signal.trade_at).collect()
    plan = state.config.profile.plan
    return PaperInstrumentEvidence(state.observed_at, "a" * 64, tuple(
        PaperInstrumentMinimum(c.symbol, c.quantity_step, c.minimum_quantity, c.minimum_notional,
                               g.price_tick, g.maximum_market_quantity, True, True)
        for c, g in zip(plan.contracts, plan.grid_rules, strict=True)),
        tuple(q.quote for q in market.quotes), market.collected_at)


def display(model, now=None, **kw):
    return capacity_snapshot(model, tenant_id=model.tenant_id, account_id=model.account_id,
        settings_revision=kw.pop("settings_revision", model.settings_revision),
        configured_limit=kw.pop("configured_limit", model.configured_limit),
        now=now or model.known_at, **kw)


class FuturesPaperCapacityTests(unittest.TestCase):
    def flat(self):
        market = Provider(now=END + timedelta(seconds=31)).collect()
        return opened(market), market

    def test_flat_own_cash_funds_only_acknowledged_three_full_ranges(self):
        state, market = self.flat()
        before = state.state_digest
        model = capacity_state(state, instruments(state, market))
        result = display(model)
        self.assertEqual((result["runtime_ready"], result["recommendation"]), (True, 3))
        self.assertEqual(model.evidence.active_baskets, 0)
        self.assertEqual(model.evidence.funded_capacity, 3)
        self.assertEqual(model.evidence.reserved_unposted_cash, state.config.profile.plan.remainder)
        self.assertEqual(result["capacity"]["range_budget"], "3333.33333333")
        self.assertEqual(state.state_digest, before)

    def test_actual_open_regular_manual_fee_and_funding_restoration_remain_reserved(self):
        state = opened()
        model = capacity_state(state, instruments(state))
        self.assertEqual(model.evidence.active_baskets, 3)
        self.assertEqual(display(model)["capacity"]["additional_baskets"], 0)
        ledger, plan = state.signal.economic.ledger, state.config.profile.plan
        expected = plan.remainder + sum(
            (b.capital - row.margin_committed - row.entry_fees
             + max(D(0), row.margin_committed - row.isolated_balance)
             for row, b in zip(ledger.baskets, plan.budgets) if row.quantity), D(0))
        self.assertEqual(model.evidence.reserved_unposted_cash, expected)
        rows = tuple(replace(b, isolated_balance=b.isolated_balance-D(1),
                             funding_net=b.funding_net-D(1)) if b.quantity else b for b in ledger.baskets)
        funded = replace(state, signal=replace(state.signal, economic=replace(
            state.signal.economic, ledger=replace(ledger, baskets=rows))))
        new = capacity_state(funded, instruments(funded))
        self.assertEqual(new.evidence.reserved_unposted_cash, expected + 3)

    def test_changed_grid_non_normal_or_unsupported_leverage_excludes_only_affected_candidates(self):
        state, market = self.flat()
        evidence = instruments(state, market)
        for changed in (replace(evidence.instruments[0], normal=False),
                        replace(evidence.instruments[0], supports_2x=False),
                        replace(evidence.instruments[0], price_tick=D(".123"))):
            value = replace(evidence, instruments=(changed, *evidence.instruments[1:]))
            self.assertEqual(capacity_state(state, value).evidence.eligible_assets, 4)
        value = replace(evidence, instruments=tuple(replace(r, normal=i < 2)
                                                   for i, r in enumerate(evidence.instruments)))
        self.assertEqual(display(capacity_state(state, value))["recommendation_reason"],
                         "candidate_pool_insufficient")

    def test_stale_cash_instruments_h1_and_unapplied_settings_have_no_recommendation(self):
        state, market = self.flat()
        model = capacity_state(state, instruments(state, market))
        self.assertEqual(display(model, model.known_at+timedelta(seconds=31))["recommendation_reason"],
                         "stale_instrument_data")
        now = model.known_at+timedelta(seconds=31)
        current_instrument = replace(model, known_at=now, instrument_at=now)
        self.assertEqual(display(current_instrument)["recommendation_reason"], "stale_futures_cash")
        now = END+timedelta(hours=1, seconds=1)
        old_hour = replace(model, known_at=now, instrument_at=now,
                           evidence=replace(model.evidence, observed_at=now))
        self.assertEqual(display(old_hour)["recommendation_reason"], "stale_futures_cash")
        self.assertEqual(display(model, settings_revision=1)["recommendation_reason"], "paper_settings_pending")
        self.assertEqual(display(model, account_ready=False)["recommendation_reason"], "account_unavailable")
        self.assertEqual(display(replace(model, blocked=True))["recommendation_reason"], "paper_runtime_blocked")
        with self.assertRaises(ValueError):
            display(model, model.known_at-timedelta(seconds=1))

    def test_missing_calibration_and_foreign_quote_scope_do_not_invent_capacity(self):
        state, market = self.flat()
        self.assertEqual(display(capacity_state(state, None))["recommendation_reason"],
                         "instrument_data_unavailable")
        evidence = instruments(state, market)
        with self.assertRaises(ValueError):
            capacity_state(state, replace(evidence, quoted_at=evidence.quoted_at-timedelta(seconds=1)))
        wrong = replace(evidence.quotes[0], bid=evidence.quotes[0].bid-D(1))
        with self.assertRaises(ValueError):
            capacity_state(state, replace(evidence, quotes=(wrong, *evidence.quotes[1:])))
        model = capacity_state(state, evidence)
        with self.assertRaises(ValueError):
            capacity_snapshot(model, tenant_id="foreign", account_id=model.account_id,
                              settings_revision=0, configured_limit=3, now=model.known_at)

    def test_v2_atomic_publication_roundtrip_no_refresh_and_legacy_reader_compatibility(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, source, provider = configured(folder)
            publisher.close()
            def read(state):
                _, _, cursor = saved.source_checkpoint()
                return instruments(state, archive.load(cursor.market)) if cursor.market else None
            callback = Mock(side_effect=read)
            try:
                with FuturesAssetPublisher(Path(folder)/"status", saved, clock=lambda: provider.now,
                                           capacity_reader=callback) as writer:
                    source = replace(source, publisher=writer)
                    source.run_once()
                    source.run_once()
                    reader = FuturesAssetReader(Path(folder)/"status", clock=lambda: provider.now)
                    value = reader.publication("tenant", "account")
                    self.assertEqual(reader.capacity("tenant", "account"), value.capacity)
                    self.assertEqual(reader("tenant", "account"), value.state)
                    count = callback.call_count
                    self.assertEqual(writer.publish(expected_revision=saved.state.revision), value)
                    self.assertEqual(callback.call_count, count)
                    self.assertIsNone(reader.capacity("foreign", "account"))
            finally:
                saved.close()

    def test_advisory_http_failure_retains_assets_and_unknown_publication_still_poisoned(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, source, provider = configured(folder)
            publisher.close()
            failed = Mock(side_effect=OSError("unavailable"))
            try:
                with FuturesAssetPublisher(Path(folder)/"status", saved, clock=lambda: provider.now,
                                           capacity_reader=failed) as writer:
                    source = replace(source, publisher=writer)
                    source.run_once()
                    current = FuturesAssetReader(Path(folder)/"status", clock=lambda: provider.now)
                    self.assertIsNotNone(current("tenant", "account"))
                    self.assertIsNone(current.capacity("tenant", "account").evidence)
                    original = writer.publish
                    def poison(**kw):
                        with patch("investalo_trading.futures_paper_status.os.fsync", side_effect=OSError("lost")):
                            return original(**kw)
                    with patch.object(writer, "publish", side_effect=poison):
                        with self.assertRaises(PaperStatusCommitUnknown):
                            source.run_once()
                    calls = failed.call_count
                    with self.assertRaises(PaperStatusCommitUnknown):
                        writer.publish(expected_revision=saved.state.revision)
                    self.assertEqual(failed.call_count, calls)
            finally:
                saved.close()

    def test_native_calibrator_uses_acknowledged_archive_and_fetches_once_without_retry(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, source, provider = configured(folder)
            fetch = Mock(side_effect=lambda: contracts_payload(saved.state))
            reader = FuturesPaperCapacitySource(saved, archive, lambda: provider.now, fetch)
            try:
                self.assertIsNone(reader(saved.state))
                fetch.assert_not_called()
                source.run_once()
                self.assertIsNone(reader(saved.state))
                source.run_once()
                before = saved.receipt
                evidence = reader(saved.state)
                self.assertEqual(capacity_state(saved.state, evidence).evidence.eligible_assets, 5)
                self.assertEqual(fetch.call_count, 1)
                fetch.side_effect = OSError("unavailable")
                with self.assertRaises(OSError):
                    reader(saved.state)
                self.assertEqual(fetch.call_count, 2)
                self.assertEqual(saved.receipt, before)
            finally:
                publisher.close()
                saved.close()
