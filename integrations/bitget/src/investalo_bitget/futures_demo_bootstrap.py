"""Native current-account evidence; incomplete collateral never becomes zero."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib

from .futures_demo import DemoBinding, DemoRejected
from .futures_demo_account import DemoPacket, DemoReadPlan, _frame
from .futures_demo_reconcile import position_quantities
from .models import ProductType
from . import parse
from investalo_trading.capital_digest import digest
from investalo_trading.futures_broker_bootstrap import BrokerFlatAccount


@dataclass(frozen=True)
class NativeStartAccount:
    account: BrokerFlatAccount | None
    blockers: tuple[str, ...]
    source_digest: str
    observed_at: datetime
    execution_enabled: bool = False


def native_start_account(wallet_response, positions_response, binding, *, context, now_ms):
    if type(binding) is not DemoBinding:
        raise DemoRejected("own_native_start_binding_required")
    _, wallet_ms = _frame(DemoPacket(DemoReadPlan(binding, "wallet"), wallet_response), binding, context, now_ms)
    raw, positions_ms = _frame(DemoPacket(DemoReadPlan(binding, "positions"), positions_response), binding, context, now_ms)
    rows, wallet_at = parse.futures_accounts(wallet_response, ProductType.USDT)
    if len(rows) != 1 or rows[0].margin_coin != "USDT":
        raise DemoRejected("own_single_usdt_start_wallet_required")
    quantities = position_quantities(raw)
    positions_at = parse.EPOCH + timedelta(milliseconds=positions_ms)
    source = digest(("bitget-demo-native-start-account/1", binding.record(),
        hashlib.sha256(wallet_response.body).hexdigest(), hashlib.sha256(positions_response.body).hexdigest(),
        wallet_ms, positions_ms))
    wallet, blockers = rows[0], []
    if wallet.asset_mode != "single" or wallet.assets not in (None, ()):
        blockers.append("wallet_profile_unconfirmed")
    extras = (wallet.crossed_margin, wallet.coupon, wallet.grant)
    if any(v is None for v in extras):
        blockers.append("collateral_unconfirmed")
    elif any(v != 0 for v in extras):
        blockers.append("foreign_collateral")
    amounts = (wallet.account_equity, wallet.available, wallet.locked,
               wallet.unrealized_pnl, wallet.isolated_margin)
    if any(v is None for v in amounts):
        blockers.append("account_amounts_unconfirmed")
    elif (wallet.account_equity <= 0 or wallet.account_equity != wallet.available
          or any(v != 0 for v in amounts[2:])):
        blockers.append("account_not_flat")
    if any(quantities.values()):
        blockers.append("positions_not_flat")
    for row in raw:
        if parse.amount(row.get("marginSize")) != Decimal(0):
            blockers.append("position_margin_unconfirmed")
            break
    account = None if blockers else BrokerFlatAccount(*amounts, 0, wallet_at, positions_at, source)
    return NativeStartAccount(account, tuple(blockers), source, max(wallet_at, positions_at))
