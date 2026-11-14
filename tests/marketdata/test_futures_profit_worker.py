"""Actual archived source/journal/status Q36 path; synthetic provider responses."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from investalo_marketdata.bitget import milliseconds
from investalo_trading.futures_capital_research import start_capital_research
from investalo_trading.futures_capital_signals import start_capital_signals
from investalo_trading.futures_paper import start_paper
from investalo_trading.futures_paper_profit_plan import paper_profit_plan
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader
from investalo_workers.futures_account_worker import FuturesAccountWorker
from investalo_workers.futures_capacity_source import FuturesPaperCapacitySource
from investalo_workers.futures_paper_bootstrap import PaperBootstrapSpec
from test_futures_account_worker import own_genesis, TENANT, ACCOUNT, BINDING, evidence
from test_futures_source_worker import configured
from test_futures_paper_feed import END, H1
from test_futures_paper_capacity import contracts_payload


def configured_profit(folder, tenant=TENANT, account=ACCOUNT):
    old = own_genesis(tenant, account)
    p = old.config.profile.plan
    plan = paper_profit_plan(p.tenant_id, p.account_id, p.policy_digest, p.contracts,
        p.grid_rules, p.grid_source_digest, initial_slots=3, configured_limit=7)
    profile = replace(old.config.profile, plan=plan)
    economic = start_capital_research(plan, old.signal.trade_prices, old.signal.as_of,
                                      "synthetic-paper-genesis")
    genesis = start_paper(replace(old.config, profile=profile),
                          start_capital_signals(profile, economic, old.signal.trade_prices))
    saved, archive, publisher, source, provider = configured(folder, genesis)
    publisher.close()
    provider.target = END + 8 * H1
    provider.quote = "100"
    original_fetch = provider.fetch

    def fetch(url):
        value = original_fetch(url)
        if "history-candles" in url or "history-mark-candles" in url:
            for row in value["data"]:
                if int(row[0]) >= milliseconds(END):
                    row[1:5] = ["2000", "2001", "1999", "2000"]
        elif "/ticker?" in url:
            for row in value["data"]:
                row.update(bidPr=provider.quote, askPr=provider.quote, markPrice=provider.quote)
        return value

    archive = replace(archive, market_fetch=fetch)
    publisher = FuturesAssetPublisher(Path(folder) / "status", saved, clock=lambda: provider.now,
        capacity_reader=FuturesPaperCapacitySource(saved, archive, lambda: provider.now,
                                                   lambda: contracts_payload(saved.state)))
    source = replace(source, archive=archive, publisher=publisher)
    return saved, archive, publisher, source, provider, genesis


def profitable_quotes(worker, provider):
    assert worker.run_once().outcome == "warmed"
    provider.now += timedelta(seconds=1)
    assert worker.run_once().entries == 3
    provider.now = END + H1 + timedelta(seconds=2)
    provider.quote = "2000"
    assert worker.run_once().closures == 0
    provider.now += timedelta(seconds=1)
    provider.quote = "1000"
    return worker.run_once()


class FuturesProfitWorkerTests(unittest.TestCase):
    def test_archived_guarded_worker_grants_once_publishes_and_full_restore_retains_source(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, source, provider, genesis = configured_profit(folder)
            worker = FuturesAccountWorker(source, lambda: evidence(provider, 1, 7))
            try:
                result = profitable_quotes(worker, provider)
                self.assertEqual(result.closures, 3)
                actual, receipt, cursor = saved.source_checkpoint()
                self.assertEqual(result.revision, receipt["sequence"])
                self.assertEqual(actual.config.profile.plan.funded_slots, 4)
                with self.assertRaisesRegex(ValueError, "cannot import"):
                    PaperBootstrapSpec(BINDING, actual.config)
                view = FuturesAssetReader(Path(folder) / "status", lambda: provider.now)
                self.assertEqual(view.publication(TENANT, ACCOUNT).journal_receipt, receipt)
                self.assertEqual(view.capacity(TENANT, ACCOUNT).evidence.funded_capacity, 4)
                self.assertEqual(len(list((Path(folder) / "archive").iterdir())), 4)
                self.assertEqual(archive.load(cursor.market).collected_at, actual.signal.trade_at)
                cash = actual.signal.economic.ledger.unposted_cash
            finally:
                publisher.close()
                saved.close()
            with FuturesPaperJournal.restore(Path(folder) / "paper.jsonl",
                    config_digest=genesis.config.config_digest, minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state, actual)
                self.assertEqual(restored.source_checkpoint()[2], cursor)
                with FuturesAssetPublisher(Path(folder) / "status", restored,
                        clock=lambda: provider.now) as writer:
                    resumed = replace(source, journal=restored, publisher=writer)
                    provider.now += timedelta(seconds=1)
                    worker = FuturesAccountWorker(resumed, lambda: evidence(provider, 1, 7))
                    worker.run_once()
                    self.assertEqual(len(restored.state.config.profile.plan.epochs), 1)
                    self.assertEqual(restored.state.signal.economic.ledger.unposted_cash, cash)
