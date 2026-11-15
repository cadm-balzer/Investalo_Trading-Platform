"""Meaningful real-reducer/replay validation of the declared acceptance vector."""
from datetime import datetime, timezone
from dataclasses import replace
from decimal import Decimal
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_recovery import PaperRecoveryRequest

spec = importlib.util.spec_from_file_location("recovery_fixture",
    Path(__file__).resolve().parents[1] / "infra/futures_recovery_fixture.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class FuturesRecoveryFixtureTests(unittest.TestCase):
    def test_actual_liquidation_recovery_and_full_replay_across_closed_hour_clocks(self):
        for hour in (0, 7, 23):
            with self.subTest(hour=hour), TemporaryDirectory() as folder:
                path = Path(folder) / "paper.jsonl"
                now = datetime(2026, 11, 15, hour, 5, tzinfo=timezone.utc)
                with fixture.create(path, str(uuid4()), str(uuid4()), now)[0] as saved:
                    before = saved.state
                    self.assertEqual(len(before.signal.economic.stopped), 1)
                    self.assertEqual(sum(bool(b.quantity) for b in before.signal.economic.ledger.baskets), 2)
                    stopped = before.signal.economic.stopped[0]
                    request = PaperRecoveryRequest(before.config.profile.plan.tenant_id,
                        before.config.profile.plan.account_id, str(uuid4()), stopped.symbol,
                        stopped.cycle, before.revision, before.state_digest, str(uuid4()), True)
                    after = saved.append("manual_recovery", request=request,
                        expected_revision=before.revision, at=now)
                    old, new = before.signal.economic.ledger, after.signal.economic.ledger
                    self.assertEqual((new.unposted_cash, new.realized_net_pnl),
                                     (old.unposted_cash, old.realized_net_pnl))
                    expected = tuple(replace(b, charges_in_budget_epoch=Decimal(0))
                        if b.symbol == stopped.symbol else b for b in old.baskets)
                    self.assertEqual(new.baskets, expected)
                    self.assertFalse(after.signal.economic.stopped)
                    self.assertEqual(after.signal.last_hour.close_time,
                                     now.replace(minute=0, second=0, microsecond=0))
                    receipt = saved.receipt
                with FuturesPaperJournal.restore(path, config_digest=before.config.config_digest,
                                                  minimum_receipt=receipt) as restored:
                    self.assertEqual(restored.state, after)
                    self.assertEqual(restored.receipt, receipt)
