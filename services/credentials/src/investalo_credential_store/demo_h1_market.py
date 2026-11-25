"""Fixed keyless Demo contracts/tickers and a native, full-margin basket plan."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import ssl
from urllib.request import Request, build_opener, HTTPSHandler, ProxyHandler

from investalo_bitget import parse
from investalo_bitget.futures_demo import SYMBOLS, DemoRejected
from investalo_bitget.transport import ReadResponse, _NoRedirect
from investalo_trading.futures_broker_plan import CapitalBrokerPlan, BrokerGridRule
from investalo_trading.futures_risk import FuturesContract, FuturesBudget
from investalo_trading.futures_economics import MarginSchedule, MarginTier
from investalo_trading.futures_capital_signals import CapitalH1SignalProfile
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.capital_digest import digest
from investalo_trading.models import floor_step, precise

D = Decimal
TARGETS = ("/api/v2/mix/market/contracts?productType=USDT-FUTURES",
           "/api/v2/mix/market/tickers?productType=USDT-FUTURES")
UNIVERSE = tuple(sorted(SYMBOLS))


def public_get(target):
    if target not in TARGETS:
        raise DemoRejected("unsupported_demo_market_target")
    tls = ssl.create_default_context()
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=tls), _NoRedirect())
    with opener.open(Request("https://api.bitget.com"+target,
            headers={"paptrading": "1", "Accept": "application/json"}), timeout=3) as r:
        body = r.read(1024*1024+1)
        if r.status != 200 or len(body) > 1024*1024:
            raise DemoRejected("demo_market_response_unconfirmed")
        return ReadResponse(200, body)


def amount(row, key):
    value = parse.amount(row.get(key))
    if value is None or value <= 0:
        raise DemoRejected("native_market_field_unconfirmed")
    return value


@dataclass(frozen=True)
class NativeMarketView:
    contracts: tuple[dict, ...]
    trade: tuple[LedgerMark, ...]
    marks: tuple[LedgerMark, ...]
    asks: tuple[tuple[str, Decimal], ...]
    observed_at: datetime
    source_digest: str


class DemoH1MarketSource:
    def __init__(self, fetch=public_get, clock=lambda: datetime.now(timezone.utc)):
        self.fetch, self.clock = fetch, clock

    def read(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = tuple(pool.map(self.fetch, TARGETS))
        parsed = tuple(parse.envelope(r) for r in replies)
        now = self.clock()
        if any(not timedelta(0) <= now-at <= timedelta(seconds=5) for _, at in parsed):
            raise DemoRejected("native_market_quote_stale")
        indexed = []
        for rows, _ in parsed:
            if type(rows) is not list or any(type(r) is not dict for r in rows):
                raise DemoRejected("native_market_rows_unconfirmed")
            selected = [r for r in rows if r.get("symbol") in UNIVERSE]
            if len(selected) != len(UNIVERSE) or len({r["symbol"] for r in selected}) != len(UNIVERSE):
                raise DemoRejected("native_seven_market_cohort_incomplete")
            indexed.append({r["symbol"]: r for r in selected})
        contracts, quotes = indexed
        rules = []
        for s in UNIVERSE:
            c = contracts[s]
            if c.get("quoteCoin") != "USDT" or c.get("symbolStatus") != "normal" or "USDT" not in c.get("supportMarginCoins", []):
                raise DemoRejected("native_contract_unavailable")
            if not amount(c, "minLever") <= 2 <= amount(c, "maxLever"):
                raise DemoRejected("native_contract_fixed2x_unavailable")
            rules.append(c)
        return NativeMarketView(tuple(rules),
            tuple(LedgerMark(s, amount(quotes[s], "lastPr")) for s in UNIVERSE),
            tuple(LedgerMark(s, amount(quotes[s], "markPrice")) for s in UNIVERSE),
            tuple((s, amount(quotes[s], "askPr")) for s in UNIVERSE), max(t for _, t in parsed),
            digest(("demo-native-market/1", tuple(hashlib.sha256(r.body).hexdigest() for r in replies))))


@precise
def native_profile(control, account, market, policy):
    policy.check(policy.binding, control.credential_revision, control.storage_version)
    if (not control.matches(policy.binding) or account is None
            or market.observed_at.date() != account.wallet_at.date()):
        raise DemoRejected("original_native_capital_profile_required")
    contracts, grids = [], []
    assumptions = digest(("native-demo-budget/1", policy.policy_digest, "declared-maintenance-.005",
                          "native-public-fees-personal-unconfirmed", "actual-native-fills-only"))
    for row in market.contracts:
        s = row["symbol"]
        place = int(row["pricePlace"])
        if not 0 <= place <= 12 or str(place) != str(row["pricePlace"]):
            raise DemoRejected("native_price_precision_unconfirmed")
        tick = amount(row, "priceEndStep") * D(1).scaleb(-place)
        step = amount(row, "sizeMultiplier")
        minimum, notional, fee = (amount(row, k) for k in ("minTradeNum", "minTradeUSDT", "takerFeeRate"))
        maximum = parse.amount(row.get("maxMarketOrderQty"))
        contracts.append(FuturesContract(s, step, minimum, notional, fee, fee,
            MarginSchedule((MarginTier(D("1000000000"), D(".005"), D(20)),)), assumptions))
        grids.append(BrokerGridRule(s, tick, maximum))
    q = D(".00000001")
    slots = min(5, control.basket_limit)
    capital = floor_step(account.equity / slots, q)
    principal = floor_step(capital / D("1.01"), q)
    plan = CapitalBrokerPlan(tenant_id=str(control.tenant_id), account_id=str(control.account_id),
        policy_digest=assumptions, initial_equity=account.equity, quantum=q,
        remainder=account.equity-slots*capital, contracts=tuple(contracts),
        budgets=tuple(FuturesBudget(c.symbol, capital, capital-principal) for c in contracts),
        grid_rules=tuple(grids), grid_source_digest=market.source_digest,
        initial_slots=slots, configured_limit=control.basket_limit,
        budget_indices=(0,)*len(contracts), approved_policy_digest=policy.policy_digest)
    return CapitalH1SignalProfile(plan, 1, D(".0005"), assumptions)
