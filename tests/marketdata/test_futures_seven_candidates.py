"""Seven native axes/archive/runtime using synthetic HTTP, never market PnL."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import parse_qs, urlsplit

from investalo_marketdata.futures_broker_calibration import parse_contracts
from investalo_marketdata.futures_paper_feed import BitgetFuturesMarketSource, request_url
from investalo_marketdata.futures_settlement_source import BitgetSettlementSource
from investalo_marketdata.futures_paper_universe import SYMBOLS, SEVEN_SYMBOLS, paper_symbols, native_symbols
from investalo_marketdata.futures_paper_archive import FuturesPaperArchive
from investalo_marketdata.snapshot import canonical
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader
from investalo_trading.futures_ledger import LedgerMark
from investalo_workers.futures_local_profile import local_config, local_seven_profit_config
from investalo_workers.futures_capacity_source import FuturesPaperCapacitySource
from investalo_workers.futures_source_worker import FuturesSourceWorker
from investalo_workers.futures_paper_bootstrap import PaperBootstrapSpec, save_spec, load_spec
from test_futures_broker_calibration import response
from test_futures_paper_feed import Provider, AT, END, NOW, H1
from test_futures_settlement_source import Provider as MinuteProvider, AT as MINUTE_AT, NOW as MINUTE_NOW
from test_futures_local_profile import TENANT, ACCOUNT, USER
from test_futures_source_worker import Provider as RuntimeProvider
from investalo_trading.futures_paper_account import PaperAccountBinding
from investalo_trading.futures_capital_research import start_capital_research
from investalo_trading.futures_capital_signals import start_capital_signals
from investalo_trading.futures_paper import start_paper, warm_paper


def metadata():
    raw = response()
    for symbol in SEVEN_SYMBOLS:
        if symbol in SYMBOLS:
            continue
        row = deepcopy(raw["data"][0])
        row.update(symbol=symbol, baseCoin=symbol[:-4])
        raw["data"].append(row)
    for row in raw["data"]:
        row.update(volumePlace="3", sizeMultiplier="0.001", minTradeNum="0.001",
                   pricePlace="2", priceEndStep="1", maxMarketOrderQty="100000")
    return canonical(raw).encode()


class SevenProvider(Provider):
    def fetch(self, url):
        query = parse_qs(urlsplit(url).query)
        symbol = query["symbol"][0]
        value = super().fetch(url.replace(symbol, SYMBOLS[0]) if symbol not in SYMBOLS else url)
        self.urls[-1] = url
        if "granularity" in query:
            value["data"] = [row for row in value["data"]
                if int(query["startTime"][0]) <= int(row[0]) <= int(query["endTime"][0])]
        for row in value["data"]:
            if isinstance(row, dict):
                row["symbol"] = symbol
        return value


class SevenMinuteProvider(MinuteProvider):
    def fetch(self, url):
        symbol = parse_qs(urlsplit(url).query)["symbol"][0]
        value = super().fetch(url.replace(symbol, SYMBOLS[0]) if symbol not in SYMBOLS else url)
        self.urls[-1] = url
        for row in value["data"]:
            if isinstance(row, dict):
                row["symbol"] = symbol
        return value


class SevenRuntimeProvider(RuntimeProvider):
    def fetch(self, url):
        symbol = parse_qs(urlsplit(url).query)["symbol"][0]
        value = super().fetch(url.replace(symbol, SYMBOLS[0]) if symbol not in SYMBOLS else url)
        self.urls[-1] = url
        for row in value["data"]:
            if isinstance(row, dict):
                row["symbol"] = symbol
        return value


def spec(tenant=TENANT, account=ACCOUNT):
    raw = metadata()
    config = local_seven_profit_config(tenant, account,
        parse_contracts(raw, symbols=SEVEN_SYMBOLS), hashlib.sha256(raw).hexdigest(), END)
    return PaperBootstrapSpec(PaperAccountBinding(tenant, account, USER,
        "https://seven.invalid", "synthetic-seven", 0, NOW), config)


def configured_seven(folder, tenant=TENANT, account=ACCOUNT):
    root = Path(folder)
    for name in ("archive", "status"):
        (root / name).mkdir(mode=0o700)
    provider = SevenRuntimeProvider()
    allocated = spec(tenant, account)
    archive = FuturesPaperArchive(root / "archive", clock=lambda: provider.now,
        market_fetch=provider.fetch, minute_fetch=provider.fetch, sleep=lambda _: None,
        symbols=SEVEN_SYMBOLS)
    # Actual feed worker must archive and acknowledge this native warmup itself.
    contracts = allocated.config.profile.plan.contracts
    trade = tuple(LedgerMark(c.symbol, Decimal(130)) for c in contracts)
    journal = FuturesPaperJournal.create(root / "paper.jsonl", allocated.config, trade, trade,
                                        AT, "synthetic-seven-genesis")
    publisher = FuturesAssetPublisher(root / "status", journal, clock=lambda: provider.now,
        capacity_reader=FuturesPaperCapacitySource(journal, archive, lambda: provider.now, metadata))
    source = FuturesSourceWorker(journal, archive, publisher, lambda: provider.now)
    return journal, archive, publisher, source, provider, allocated


class FuturesSevenCandidatesTests(unittest.TestCase):
    def test_new_native_seven_profile_actually_funds_and_trades_all_seven_after_profit_epochs(self):
        from test_futures_paper_runtime import frames
        from test_futures_paper_profit import cycle, grant
        config = spec().config
        prices = tuple(LedgerMark(s, Decimal(130)) for s in config.profile.plan.symbols)
        economic = start_capital_research(config.profile.plan, prices, AT, "synthetic-seven-genesis")
        state = start_paper(config, start_capital_signals(config.profile, economic, prices))
        state = warm_paper(state, frames(state, range(130, 98, -2)), 0, END)
        for funded in (4, 5, 6, 7):
            state = grant(cycle(state))
            self.assertEqual(state.config.profile.plan.funded_slots, funded)
        closed_before = state.signal.economic.ledger.closed_baskets
        state = cycle(state)
        self.assertEqual(state.signal.economic.ledger.closed_baskets - closed_before, 7)
        self.assertEqual({s.symbol for s in state.signal.economic.stages},
                         {"BITGET:" + s for s in SEVEN_SYMBOLS})
        self.assertEqual(state.config.profile.plan.target_range, Decimal("3333.33333333"))
        state = grant(state)
        self.assertEqual(state.config.profile.plan.target_range, Decimal("3809.52380952"))

    def test_explicit_pool_metadata_identity_status_and_default_are_preserved(self):
        raw = metadata()
        self.assertEqual(tuple(r.symbol for r in parse_contracts(raw)), SYMBOLS)
        seven = parse_contracts(raw, symbols=SEVEN_SYMBOLS)
        self.assertEqual(tuple(r.symbol for r in seven), SEVEN_SYMBOLS)
        allocated = spec()
        plan = allocated.config.profile.plan
        self.assertEqual((plan.funded_slots, plan.configured_limit, plan.simultaneous_limit), (3, 7, 3))
        self.assertEqual(len(plan.symbols), 7)
        self.assertEqual(plan.budgets[0].capital, spec().config.profile.plan.original_range)
        fixed = local_config(TENANT, ACCOUNT, parse_contracts(raw), "a" * 64, END)
        self.assertEqual(len(fixed.profile.plan.symbols), 5)
        with self.assertRaises(ValueError):
            local_config(TENANT, ACCOUNT, seven, "a" * 64, END)
        for bad in (SEVEN_SYMBOLS[:-1], tuple(reversed(SEVEN_SYMBOLS)), list(SEVEN_SYMBOLS),
                    (*SYMBOLS, "LINKUSDT", "UNAPPROVEDUSDT")):
            with self.subTest(pool=bad), self.assertRaises(ValueError):
                paper_symbols(bad)
        with self.assertRaises(ValueError):
            native_symbols(tuple("BINANCE:" + s for s in SEVEN_SYMBOLS))
        for bad in (seven[:-1], (replace(seven[0], status="off"), *seven[1:]),
                    (*seven[:-1], replace(seven[-1], max_leverage=1))):
            with self.subTest(rules=bad), self.assertRaises(ValueError):
                local_seven_profit_config(TENANT, ACCOUNT, bad, "a" * 64, END)
        with TemporaryDirectory() as folder:
            saved = Path(folder) / "allocation.json"
            save_spec(saved, allocated)
            self.assertEqual(load_spec(saved, allocated.spec_digest), allocated)

    def test_collector_exact_new_axes_quotes_and_missing_native_data(self):
        provider = SevenProvider()
        observation = BitgetFuturesMarketSource(
            provider.fetch, lambda: NOW, lambda _: None, symbols=SEVEN_SYMBOLS).collect(
                start=AT, end=END, funding_start=AT)
        self.assertEqual(len(provider.urls), 35)
        self.assertEqual(observation.symbols, SEVEN_SYMBOLS)
        self.assertEqual(observation.record()["schema_version"], "bitget-classic-futures-paper-source/2")
        self.assertEqual(len(observation.hours), 16)
        self.assertEqual(len(observation.hours[0].trade), 7)
        self.assertEqual(len(observation.quotes), 7)
        self.assertEqual(len(observation.forecasts), 7)
        self.assertTrue(observation.hours[0].trade[0].symbol.startswith("BITGET:AVAXUSDT:"))
        self.assertNotEqual(observation.hours[0].trade[-1].close, observation.hours[0].mark[-1].close)
        five = Provider().collect()
        self.assertEqual(five.record()["schema_version"], "bitget-classic-futures-paper-source/1")
        # Omitted last native axis must fail, never duplicate another coin as fallback.
        def missing(url):
            value = provider.fetch(url)
            if "AVAXUSDT" in url and "/history-mark-candles?" in url:
                value["data"].pop(2)
            return value
        with self.assertRaisesRegex(ValueError, "coverage"):
            BitgetFuturesMarketSource(missing, lambda: NOW, lambda _: None,
                symbols=SEVEN_SYMBOLS).collect(start=AT, end=END, funding_start=AT)
        with self.assertRaises(ValueError):
            request_url("BGBUSDT", "quote")

    def test_full_archived_worker_capacity_and_restart_keep_seven_but_three_funded(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "archive").mkdir(mode=0o700)
            (root / "status").mkdir(mode=0o700)
            provider = SevenProvider()
            archive = FuturesPaperArchive(root / "archive", clock=lambda: provider.now,
                market_fetch=provider.fetch, sleep=lambda _: None, symbols=SEVEN_SYMBOLS)
            allocated = spec()
            # Bootstrap uses the actual captured warmup, not a fabricated initial axis.
            warm_ref, warm = archive.market(start=AT, end=END, funding_start=AT)
            plan = allocated.config.profile.plan
            trade = tuple(LedgerMark(s, c.open) for s, c in zip(
                plan.symbols, warm.hours[0].trade, strict=True))
            mark = tuple(LedgerMark(s, c.open) for s, c in zip(
                plan.symbols, warm.hours[0].mark, strict=True))
            path = root / "journal.jsonl"
            with FuturesPaperJournal.create(path, allocated.config, trade, mark, AT,
                                            "synthetic-seven-genesis") as journal:
                journal.append("source_warmup", expected_revision=0, at=NOW,
                               hours=warm.hours, source=warm_ref)
                capacity = FuturesPaperCapacitySource(journal, archive, lambda: provider.now, metadata)
                with FuturesAssetPublisher(root / "status", journal, clock=lambda: provider.now,
                                           capacity_reader=capacity) as publisher:
                    worker = FuturesSourceWorker(journal, archive, publisher, lambda: provider.now)
                    result = worker.run_once()
                    self.assertEqual(result.entries, 3)
                    actual, receipt, cursor = journal.source_checkpoint()
                    self.assertEqual(len(actual.signal.economic.ledger.baskets), 7)
                    view = FuturesAssetReader(root / "status", lambda: provider.now)
                    self.assertEqual(view.capacity(TENANT, ACCOUNT).evidence.funded_capacity, 3)
                    self.assertEqual(view.capacity(TENANT, ACCOUNT).evidence.eligible_assets, 7)
                    self.assertEqual(len(view(TENANT, ACCOUNT).assets), 7)
                    self.assertEqual(archive.load(cursor.market).symbols, SEVEN_SYMBOLS)
                    with self.assertRaises(ValueError):
                        Provider().collect().paper_batch(actual)
            with FuturesPaperJournal.restore(path, config_digest=allocated.config.config_digest,
                                              minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state, actual)
                self.assertEqual(restored.source_checkpoint()[2], cursor)
                self.assertEqual(archive.load(cursor.warmup), warm)

    def test_fourteen_native_settlement_reads_replay_without_universe_mixing(self):
        with TemporaryDirectory() as folder:
            provider = SevenMinuteProvider()
            archive = FuturesPaperArchive(Path(folder), clock=lambda: MINUTE_NOW,
                minute_fetch=provider.fetch, sleep=lambda _: None, symbols=SEVEN_SYMBOLS)
            ref, evidence = archive.minute(MINUTE_AT)
            self.assertEqual(len(provider.urls), 14)
            self.assertEqual(len(evidence.funding), 7)
            self.assertEqual(evidence.symbols, SEVEN_SYMBOLS)
            self.assertEqual(evidence.record()["schema_version"], "bitget-classic-futures-settlement-evidence/2")
            self.assertEqual(archive.load(ref), evidence)
            with self.assertRaises(ValueError):
                evidence.paper_minute_settlement(None, observation=Provider().collect(), previous=None)
            broken = Path(folder) / ref.key / "response-14.json"
            broken.write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                archive.load(ref)

    def test_seven_funding_ids_and_mark_minutes_are_committed_and_restored(self):
        with TemporaryDirectory() as folder:
            journal, archive, publisher, worker, provider, allocated = configured_seven(folder)
            try:
                self.assertEqual(worker.run_once().outcome, "warmed")
                provider.now += timedelta(seconds=1)
                self.assertEqual(worker.run_once().entries, 3)
                provider.now = provider.target + timedelta(seconds=65)
                result = worker.run_once()
                self.assertEqual(result.outcome, "funding_and_quotes")
                actual, receipt, cursor = journal.source_checkpoint()
                self.assertIsNone(cursor.pending)
                self.assertEqual(len(actual.funding_ids), 7)
                cash = actual.signal.economic.ledger.unposted_cash
            finally:
                publisher.close()
                journal.close()
            with FuturesPaperJournal.restore(Path(folder) / "paper.jsonl",
                    config_digest=allocated.config.config_digest, minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state, actual)
                with FuturesAssetPublisher(Path(folder) / "status", restored,
                                           clock=lambda: provider.now) as writer:
                    provider.now += timedelta(seconds=1)
                    resumed = replace(worker, journal=restored, publisher=writer)
                    self.assertEqual(resumed.run_once().outcome, "quotes")
                    self.assertEqual(len(restored.state.funding_ids), 7)
                    self.assertEqual(restored.state.signal.economic.ledger.unposted_cash, cash)
