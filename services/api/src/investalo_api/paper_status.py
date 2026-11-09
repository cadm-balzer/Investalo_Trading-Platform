"""Bounded public Paper projection; raw domain state and free text stay private."""
from datetime import datetime, timezone, date
from decimal import Decimal, localcontext
from uuid import UUID

from fastapi import HTTPException
from investalo_marketdata.snapshot import price, parse_time, decimal_string

SYMBOLS = ("BTCUSDT", "ETHUSDT")
EVENTS = {
    "entry_blocked": "Einstieg blockiert.",
    "risk_stop": "Risikogrenze ausgelöst.",
    "protection_updated": "Schutzgrenze aktualisiert.",
    "manual_reserve_available": "Manuelle Reserve kann geprüft werden.",
    "simulated_order_cancelled": "Paperauftrag storniert.",
    "data_rejected": "Marktdaten abgewiesen.",
    "cancel_order": "Stornierung vorgemerkt.",
}


def stamp(value):
    return parse_time(value).isoformat()


def amount(value):
    return price(value, zero=True)


def publish_rows(rows, tenant_id, *, now=None):
    now = now or datetime.now(timezone.utc)
    if len(rows) > 20:
        raise ValueError()
    result = []
    with localcontext() as ctx:
        ctx.prec = 36
        for row in rows:
            account_id = str(UUID(str(row["account_id"])))
            if row["account_status"] not in ("ready", "paused", "disconnected"):
                raise ValueError()
            name = row["account_name"]
            if not isinstance(name, str) or not 1 <= len(name) <= 200:
                raise ValueError()
            snapshot = row["snapshot"]
            view = None
            if snapshot is not None:
                if snapshot.get("checksum_valid") is not True:
                    raise ValueError()
                a = snapshot["account"]
                if a["tenant_id"] != str(tenant_id) or a["account_id"] != account_id:
                    raise ValueError()
                revision = snapshot["revision"]
                observed = stamp(snapshot["observed_at"])
                if type(revision) is not int or revision < 0 or parse_time(observed) > now:
                    raise ValueError()
                cash, baseline = amount(a["cash"]), amount(a["day_start_equity"])
                trading_day = date.fromisoformat(a["trading_day"])
                if trading_day > now.date() or type(a["halted"]) is not bool:
                    raise ValueError()
                positions, quotes = snapshot["positions"], snapshot["quotes"]
                if (len(positions) != 2 or tuple(p["symbol"] for p in positions) != SYMBOLS
                        or len(quotes) > 2 or len({q["symbol"] for q in quotes}) != len(quotes)
                        or any(q["symbol"] not in SYMBOLS for q in quotes)):
                    raise ValueError()
                lookup = {}
                for q in quotes:
                    at = parse_time(q["observed_at"])
                    bid, ask = price(q["bid"]), price(q["ask"])
                    if bid > ask or at > now:
                        raise ValueError()
                    lookup[q["symbol"]] = (bid, at)
                equity, fresh, public_positions = cash, True, []
                for p in positions:
                    quantity, entries = amount(p["quantity"]), p["entries"]
                    if len(entries) > 6:
                        raise ValueError()
                    principal = sum((amount(e["principal"]) for e in entries), Decimal(0))
                    bought = sum((amount(e["quantity"]) for e in entries), Decimal(0))
                    q = lookup.get(p["symbol"])
                    if quantity:
                        if q is None:
                            equity = None
                            fresh = False
                        else:
                            if equity is not None:
                                equity += quantity*q[0]
                            fresh &= 0 <= (now-q[1]).total_seconds() <= 30
                    if type(p["protected"]) is not bool or type(p["risk_stopped"]) is not bool:
                        raise ValueError()
                    public_positions.append({
                        "symbol": p["symbol"], "quantity": decimal_string(quantity),
                        "average_price": decimal_string(principal/bought) if bought else None,
                        "protected": p["protected"], "risk_stopped": p["risk_stopped"],
                    })
                view = {
                    "revision": revision, "observed_at": observed, "cash": decimal_string(cash),
                    "equity": decimal_string(equity) if equity is not None else None,
                    "valuation_fresh": fresh, "trading_day": str(trading_day),
                    "day_start_equity": decimal_string(baseline),
                    "daily_baseline_ready": trading_day == now.date(), "halted": a["halted"],
                    "positions": public_positions,
                }
            journal = row["journal"]
            if not isinstance(journal, list) or len(journal) > 20:
                raise ValueError()
            public_journal = []
            previous_revision = snapshot["revision"]+1 if snapshot is not None else 0
            for j in journal:
                if (type(j["revision"]) is not int or j["revision"] <= 0
                        or j["revision"] >= previous_revision
                        or j["input_kind"] not in ("quote", "bar")
                        or type(j["fill_count"]) is not int or not 0 <= j["fill_count"] <= 20
                        or not isinstance(j["events"], list) or len(j["events"]) > 100):
                    raise ValueError()
                previous_revision = j["revision"]
                messages = [EVENTS[e["kind"]] for e in j["events"]
                            if isinstance(e, dict) and e.get("kind") in EVENTS]
                public_journal.append({
                    "revision": j["revision"], "at": stamp(j["at"]),
                    "input_kind": j["input_kind"], "fill_count": j["fill_count"],
                    "messages": messages,
                })
            result.append({"id": account_id, "name": name, "status": row["account_status"],
                           "snapshot": view, "journal": public_journal})
    return {"schema_version": "paper-status/1", "mode": "paper", "live_enabled": False,
            "tenant_id": str(tenant_id), "accounts": result}


def read_status(db, user, identity):
    rows = db.execute(
        "SELECT * FROM platform.paper_status_rows(%s,%s)",
        (user["auth_epoch"], datetime.fromtimestamp(identity.oidc_auth_time, timezone.utc)),
    ).fetchall()
    try:
        return publish_rows(rows, identity.tenant_id)
    except (ValueError, KeyError, TypeError, ArithmeticError):
        raise HTTPException(503, "Paper status unavailable") from None
