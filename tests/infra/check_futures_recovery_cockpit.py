"""Real private HTTPS/BFF/API/PG/SSR; declared synthetic liquidation/source only.

Only the source factory and between-cycle wait are injected. The journal, sole
writer locks, launcher, original allocation, actor reads and API executor are real.
No physical browser click, native market performance or broker authority claimed.
"""
from datetime import datetime, timezone
from dataclasses import replace
from decimal import Decimal
import os
from pathlib import Path
import stat
from time import sleep
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import check_passkey_browser as browser
from check_futures_local_cockpit import fixture, save, api_get
from futures_recovery_fixture import create, feed
from investalo_api.settings import Settings
from investalo_trading.futures_paper_account import PaperAccountBinding
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader, _directory
from investalo_workers.futures_account_main import main as launch
from investalo_workers.futures_account_reader import FuturesPaperAccountReader
from investalo_workers.futures_paper_bootstrap import PaperBootstrapSpec, save_spec
from investalo_workers.futures_recovery_executor import register_recovery

ROOT = Path("/app/acceptance")
CHECKS = 0
STAGE = "configuration"


def check(value, name):
    global CHECKS
    if not value:
        raise browser.CheckFailure(name)
    CHECKS += 1


def body(card):
    return {**{k: card[k] for k in
        ("account_id", "symbol", "cycle", "revision", "state_digest")},
        "event_id": str(uuid4()), "consent": True}


def run():
    global STAGE
    check(os.getenv("FUTURES_RECOVERY_ACCEPTANCE_ENABLED") == "1" and os.geteuid() == 10003,
          "explicit isolated recovery opt-in")
    fd = _directory(ROOT)
    try:
        marker = os.open(".fixture", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            info = os.fstat(marker)
            check(stat.S_ISREG(info.st_mode) and info.st_uid == 10003 and info.st_nlink == 1
                  and stat.S_IMODE(info.st_mode) == 0o400
                  and os.read(marker, 128) == b"synthetic-local-futures-recovery-acceptance/1\n",
                  "protected recovery fixture")
        finally:
            os.close(marker)
    finally:
        os.close(fd)
    now = datetime.now(timezone.utc)
    check(now.minute < 57 and (now.minute > 0 or now.second > 5), "bounded fixture clock")
    actor = fixture()
    session = browser.session(actor)
    status, _, _ = browser.request("/api/futures/settings", session,
        {"account_id": str(actor["account"]), "expected_revision": 0, "basket_limit": 7})
    check(status == 200, "actual own planning CAS")
    root = ROOT / uuid4().hex
    root.mkdir(mode=0o700)
    archive = root / "archive"
    archive.mkdir(mode=0o700)
    binding = PaperAccountBinding(str(actor["tenant"]), str(actor["account"]), str(actor["user"]),
        browser.ISSUER, actor["subject"], 0,
        datetime.fromtimestamp(actor["auth_time"], timezone.utc))
    runtime = {"PGUSER": "investalo_runtime", "PGPASSWORD_FILE": "/run/secrets/platform_runtime_password"}
    with patch.dict(os.environ, runtime):
        reader = FuturesPaperAccountReader(binding, Settings.from_environment().connection_parameters())
    journal_path = root / "paper.jsonl"
    STAGE = "synthetic case through actual reducers"
    journal, config = create(journal_path, binding.tenant_id, binding.account_id,
                             datetime.now(timezone.utc))
    spec_path = root / "allocation.json"
    spec_sha = save_spec(spec_path, PaperBootstrapSpec(binding, config))
    register_recovery(ROOT / "registry", spec_path, spec_sha, journal_path)
    with journal:
        journal.append("account_settings", evidence=reader(), expected_revision=journal.state.revision,
                       at=datetime.now(timezone.utc))
        with FuturesAssetPublisher(ROOT / "status", journal, recovery_enabled=True) as pub:
            pub.publish(expected_revision=journal.state.revision)

    def publication():
        result = FuturesAssetReader(ROOT / "status").publication(binding.tenant_id, binding.account_id)
        check(result is not None, "acknowledged publication present")
        return result

    def restore():
        return FuturesPaperJournal.restore(journal_path, config_digest=config.config_digest,
                                          minimum_receipt=publication().journal_receipt)

    def view():
        return api_get(session, "/v1/futures-recovery", collection="assets", count=None)

    def refresh():
        with restore() as saved:
            feed(saved, datetime.now(timezone.utc),
                 tuple(b.mark for b in saved.state.signal.economic.ledger.baskets))
            with FuturesAssetPublisher(ROOT / "status", saved, recovery_enabled=True) as pub:
                pub.publish(expected_revision=saved.state.revision)

    STAGE = "actual HTTPS recovery and SSR"
    initial = view()
    check(len(initial["assets"]) == 1, "one genuine booked synthetic liquidation")
    card = initial["assets"][0]
    check(card["allowed"] and card["leverage"] == "2" and float(card["net_loss"]) > 0,
          "own full budget and fixed2x recovery")
    save(root, "recovery-initial.json", initial)
    for path, text in (("/", "Handelsblocker: Liquidation"), ("/portfolio", "Gesperrte Futures-Assets")):
        status, html, _ = browser.request(path, session)
        check(status == 200 and text in html and card["symbol"] in html, "actual SSR blocked asset")
        check("Der aktuelle Futures-Paperstatus ist nicht verfügbar." not in html,
              "strict SSR recovery contract accepted")
        if path == "/portfolio":
            check("Gebuchter Nettoverlust" in html and "Kapital für neuen Basket" in html
                  and 'type="checkbox"' in html and "Wiederbeleben" in html
                  and "disabled" in html, "real loss, budget and initial consent control rendered")
    before = publication().journal_receipt
    negative = [
        (None, body(card), {}, 401),
        (session, body(card), {"X-CSRF-Token": "incorrect"}, 400),
        (session, body(card), {"Origin": "https://foreign.invalid"}, 400),
        (session, {**body(card), "consent": False}, {}, 400),
        (session, {**body(card), "cash": "1000000"}, {}, 400),
        (session, {**body(card), "actor_id": binding.user_id}, {}, 400),
    ]
    for current_session, request, headers, expected in negative:
        status, _, _ = browser.request("/api/futures/recovery", current_session, request, headers=headers)
        check(status == expected, "actual BFF guard rejected")
    check(publication().journal_receipt == before, "BFF guards never write")
    STAGE = "actual clock staleness"
    sleep(31)
    stale = view()["assets"][0]
    check(not stale["allowed"] and "reconciliation_stale" in stale["reasons"], "real stale quote blocks")
    status, _, _ = browser.request("/api/futures/recovery", session, body(stale))
    check(status == 409 and publication().journal_receipt == before,
          f"stale action cannot write (HTTP {status})")
    refresh()
    old_request = body(view()["assets"][0])

    STAGE = "bounded running launcher and manual API interleaving"
    seen = []
    manual_receipt = []

    def source_worker(source, current_reader):
        def run_once(*, guard):
            guard()
            current_reader()
            saved = source.journal
            before_state = saved.state
            seen.append(before_state)
            feed(saved, datetime.now(timezone.utc),
                 tuple(b.mark for b in saved.state.signal.economic.ledger.baskets))
            source.publisher.publish(expected_revision=saved.state.revision)
            if len(seen) == 1:
                busy_card = view()["assets"][0]
                receipt = saved.receipt
                status, _, _ = browser.request("/api/futures/recovery", session, body(busy_card))
                check(status == 503 and saved.receipt == receipt, "real active-cycle writer excludes API")
            return SimpleNamespace(outcome="quotes", revision=saved.state.revision,
                entries=len(saved.state.signal.economic.stages) - len(before_state.signal.economic.stages),
                closures=saved.state.signal.economic.ledger.closed_baskets
                         - before_state.signal.economic.ledger.closed_baskets)
        return SimpleNamespace(run_once=run_once)

    class BetweenCycles:
        def is_set(self):
            return False

        def wait(self, interval):
            check(interval == 5, "bounded interval")
            old_receipt = publication().journal_receipt
            status, _, _ = browser.request("/api/futures/recovery", session, old_request)
            check(status == 409 and publication().journal_receipt == old_receipt,
                  "previous revision cannot release")
            with restore() as saved:
                before_state = saved.state
            current_card = view()["assets"][0]
            check(current_card["allowed"], "fresh own recovery still allowed")
            status, result, _ = browser.request("/api/futures/recovery", session, body(current_card))
            check(status == 200 and result["assets"] == [], "actual manual BFF API commit between cycles")
            with restore() as saved:
                after = saved.state
                manual_receipt.append(saved.receipt)
                old, new = before_state.signal.economic.ledger, after.signal.economic.ledger
                check(after.revision == before_state.revision + 1 and not after.signal.economic.stopped,
                      "full restore acknowledges single manual action")
                check((new.unposted_cash, new.realized_net_pnl, new.day_start_equity, new.closed_baskets)
                      == (old.unposted_cash, old.realized_net_pnl, old.day_start_equity, old.closed_baskets),
                      "cash, losses, day basis and closing history retained")
                expected = tuple(replace(b, charges_in_budget_epoch=Decimal(0))
                    if b.symbol == "BITGET:" + current_card["symbol"] else b for b in old.baskets)
                check(new.baskets == expected and after.signal.economic.stages == before_state.signal.economic.stages,
                      "only target future cost counter resets; peers and purchase history retained")
                index = config.profile.plan.symbols.index("BITGET:" + current_card["symbol"])
                new_signal = after.signal.signals[index]
                check(new_signal.cycle == before_state.signal.signals[index].cycle + 1
                      and new_signal.below_count == 0 and not new_signal.rearmed,
                      "recovered target needs a fresh RSI cycle")
            for path, text in (("/", "Handelsblocker: Liquidation"), ("/portfolio", "Gesperrte Futures-Assets")):
                status, html, _ = browser.request(path, session)
                check(status == 200 and text not in html and "Handelsassets" in html,
                      "actual SSR clears blocker after committed recovery")

    args = ["--spec", str(spec_path), "--spec-digest", spec_sha, "--journal", str(journal_path),
            "--archive-root", str(archive), "--status-root", str(ROOT / "status"),
            "--recovery-root", str(ROOT / "registry"), "--cycles", "2", "--interval", "5"]
    # Declared source injection: the synthetic fixture has no native archive.
    with patch.dict(os.environ, runtime), \
            patch("investalo_workers.futures_account_main.Event", BetweenCycles), \
            patch("investalo_workers.futures_account_main.FuturesAccountWorker", side_effect=source_worker):
        launch(args)
    check(len(seen) == 2 and len(manual_receipt) == 1 and not seen[1].signal.economic.stopped
          and seen[1].revision == manual_receipt[0]["sequence"], "next worker cycle fully restores API action")
    check(view()["assets"] == [], "own final API has no liquidation blocker")
    with restore() as saved:
        final = saved.receipt
    receipt = {
        "schema_version": "futures-recovery-cockpit-acceptance/1", "checks": CHECKS,
        "synthetic_identity_session_prices_contracts": True, "native_market_sources": False,
        "worker_source_injected": True, "physical_browser_verified": False,
        "actual_https_bff_api_pg_ssr": True, "bounded_launcher_cycles": 2,
        "guard_stale_busy_revision_checks": True, "manual_full_restore_and_loss_retention": True,
        "public_enabled": False, "execution_enabled": False, "ai_enabled": False,
        "manual_journal_receipt": manual_receipt[0], "final_journal_receipt": final,
    }
    sha = save(root, "acceptance-receipt.json", receipt)
    print(f"PASS: {CHECKS} actual HTTPS/PG/SSR recovery checks; synthetic source; receipt sha256={sha}")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(f"FAIL: isolated recovery acceptance at {STAGE} ({type(error).__name__}); no receipt", flush=True)
        if isinstance(error, browser.CheckFailure):
            print(str(error), flush=True)
        raise SystemExit(1) from None
