"""Complete native order/bill/account receipt for atomic concurrent funding."""
from datetime import timedelta
from decimal import Decimal

from . import parse
from .futures_demo import DemoRejected
from .futures_demo_basket import BasketExitIntent, BasketMarketIntent
from .futures_demo_margin import _settlement_sources, Q, MONEY_TOLERANCE
from investalo_trading.capital_digest import digest
from investalo_trading.futures_broker_entries import BrokerEntryObservation, BrokerExitObservation
from investalo_trading.futures_broker_funding import BrokerFundingBill
from investalo_trading.futures_broker_settlement import BrokerOrderFundingSettlement
from investalo_trading.models import precise

D=Decimal


@precise
def reconcile_order_funding(baseline,wallet,positions,pages,intent,observation,book,*,
                            context,now_ms,expected_positions,attempted_ms,policy=None):
    if type(intent) not in (BasketMarketIntent,BasketExitIntent) or book.pending is None:
        raise DemoRejected("own_pending_order_funding_required")
    sources=_settlement_sources(baseline,wallet,positions,pages,intent,observation,
        context=context,now_ms=now_ms,expected_positions=expected_positions,attempted_ms=attempted_ms,policy=policy)
    if sources is None:
        return None
    after,rows,hashes,last_at=sources
    target=intent.grid.symbol
    owned={b.symbol:b for b in book.signal.economic.ledger.baskets if b.quantity}
    before={p.symbol:p for p in baseline.positions}
    current={p.symbol:p for p in after.positions}
    trade_kind="sell" if type(intent) is BasketExitIntent else "buy"
    trade,funding=[],[]
    for row in rows:
        if (row["fee"]>0 or row["coupon_fee"] not in (None,D(0))
                or row["kind"] not in (trade_kind,"contract_settle_fee")):
            return None
        if row["kind"]==trade_kind:
            if row["symbol"]!=target or row["created_ms"]<observation.created_ms:
                return None
            trade.append(row)
        else:
            old=owned.get(row["symbol"])
            if (old is None or row["fee"]!=0 or not baseline.observed_ms<row["created_ms"]
                    or row["symbol"]==target and (
                        type(intent) is not BasketExitIntent or observation.quantity!=intent.before_quantity
                        or row["created_ms"]>observation.updated_ms)):
                return None
            funding.append(BrokerFundingBill(
                digest(("bitget-demo-funding-bill/1",intent.binding.record(),row["id"])),
                old.symbol,old.cycle,old.quantity,row["amount"],
                parse.EPOCH+timedelta(milliseconds=row["created_ms"])))
    if not funding:
        return None
    fee=sum((r["fee"] for r in trade),D(0))
    pnl=sum((r["amount"] for r in trade),D(0))
    if (abs(fee-observation.reported_fee)>Q or bool(trade)!=bool(observation.quantity)
            or type(intent) is BasketMarketIntent and pnl!=0
            or type(intent) is BasketExitIntent and abs(
                pnl-(observation.quantity*(observation.average_price-intent.before_average)
                     if observation.quantity else D(0)))>MONEY_TOLERANCE):
        return None
    total_funding=sum((b.amount for b in funding),D(0))
    if abs(after.collateral_without_upl-baseline.collateral_without_upl-pnl-fee-total_funding)>MONEY_TOLERANCE:
        return None
    target_funding=any(b.symbol==target for b in funding)
    old,new=before.get(target),current.get(target)
    if type(intent) is BasketMarketIntent:
        if observation.quantity:
            if new is None:
                return None
            margin=new.allocated_margin-(old.allocated_margin if old is not None else D(0))
            if abs(margin-observation.quantity*observation.average_price/2)>MONEY_TOLERANCE:
                return None  # Sanity only, return the corroborated native delta.
        else:
            margin=D(0)
    elif target_funding:
        if old is None or new is not None:
            return None
        margin=old.allocated_margin  # Net occupied-margin release of this joint window.
    else:
        if old is None:
            return None
        margin=old.allocated_margin-(new.allocated_margin if new is not None else D(0))
    funding=tuple(sorted(funding,key=lambda b:(b.settled_at,b.symbol,b.id_digest)))
    proof=digest(("bitget-demo-order-funding/1",book.state_digest,baseline,after,hashes,observation,funding))
    purpose="bitget-demo-h1-basket-exit/1" if type(intent) is BasketExitIntent else "bitget-demo-h1-basket-entry/1"
    args=(intent.order_digest,observation.state,observation.quantity,observation.average_price,
          observation.reported_fee,margin)
    tail=(True,parse.EPOCH+timedelta(milliseconds=observation.response_ms),proof,
          digest((purpose,observation.order_id,observation.created_ms)),observation.updated_ms,after.observed_ms)
    entry=exit=None
    if type(intent) is BasketMarketIntent:
        entry=BrokerEntryObservation(*args,*tail)
    else:
        exit=BrokerExitObservation(*args,pnl,*tail)
    return BrokerOrderFundingSettlement(book.state_digest,baseline,after,entry,exit,
        funding,
        parse.EPOCH+timedelta(milliseconds=last_at),proof)
