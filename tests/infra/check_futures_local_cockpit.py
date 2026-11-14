"""Native public data -> bound Paper CLI -> private HTTPS/BFF/PG/SSR acceptance.

Synthetic identity/session ONLY in the protected existing fixture mount.
No live credentials, orders, account balance imports or production flags.
Failed runs remain create-only without an acceptance receipt.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
from http.client import HTTPSConnection
import json
import os
from pathlib import Path
import stat
import socket
import ssl
from time import sleep, time
from unittest.mock import patch
from uuid import uuid4

import check_passkey_browser as browser
from investalo_marketdata.futures_broker_calibration import capture_contracts, parse_contracts, SYMBOLS
from investalo_marketdata.futures_paper_archive import _write
from investalo_marketdata.snapshot import canonical
from investalo_trading.futures_paper_account import PaperAccountBinding
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetReader, _directory
from investalo_workers.futures_account_main import main as worker_main
from investalo_workers.futures_local_profile import ASSUMPTIONS, local_config
from investalo_workers.futures_paper_bootstrap import PaperBootstrapSpec, save_spec

ROOT = Path("/app/acceptance")
CHECKS = 0
STAGE = "configuration"


def check(value, name):
    global CHECKS
    if not value:
        raise browser.CheckFailure(name)
    CHECKS += 1


def save(root, name, value):
    fd = _directory(root)
    try:
        sha = _write(fd, name, value, 3 * 1024 * 1024)
        os.fsync(fd)
        return sha
    finally:
        os.close(fd)


def fixture():
    with browser.fixture_state():
        pass
    with browser.admin() as db:
        identity = db.execute("SELECT current_database() AS database,session_user AS login").fetchone()
        check(identity == {"database": "investalo_credentials_checks", "login": "investalo_migration"},
              "fixture database and operator")
        check(db.execute("SELECT 1 FROM platform.schema_migrations WHERE "
                         "version='013_futures_paper_settings'").fetchone(), "fixture013 present")
        tenant, user, account = [uuid4() for _ in range(3)]
        subject = "synthetic-futures-local-" + uuid4().hex
        db.execute("INSERT INTO platform.tenants(id,name) VALUES(%s,'Synthetic local Futures')", (tenant,))
        db.execute("INSERT INTO platform.users(id,oidc_issuer,oidc_subject) VALUES(%s,%s,%s)",
                   (user, browser.ISSUER, subject))
        db.execute("INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'owner')",
                   (tenant, user))
        db.execute("INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status) "
                   "VALUES(%s,%s,'Synthetic native Futures Paper','bitget','paper','USDT','ready')",
                   (tenant, account))
    return {"tenant": tenant, "user": user, "account": account, "subject": subject,
            "auth_time": int(time())}


def api_get(session, path):
    now = int(time())
    value = session["value"]
    claims = {
        "iss": "investalo-bff", "aud": "investalo-api", "sub": value["subject"],
        "oidc_iss": value["issuer"], "iat": now, "exp": now + 30,
        "oidc_auth_time": value["oidcAuthTime"], "jti": str(uuid4()),
        "tenant_id": value["tenantId"], "auth_epoch": value["authEpoch"],
        "htm": "GET", "htu": path, "body_sha256": hashlib.sha256(b"").hexdigest(),
    }
    prefix = browser.b64(browser.wire({"alg": "HS256", "typ": "JWT"})) + "." + browser.b64(browser.wire(claims))
    secret = Path("/run/secrets/browser_check_internal_secret").read_text().strip()
    signature = browser.b64(hmac.digest(secret.encode(), prefix.encode(), "sha256"))
    # The database network also has a normal service named "api". Connect to
    # the exact fixture service, retaining TLS certificate validation for api.
    connection = HTTPSConnection("api", 8000, timeout=15,
        context=ssl.create_default_context(cafile=os.environ["PGSSLROOTCERT"]))
    connection._create_connection = lambda _address, timeout, source_address: socket.create_connection(
        ("browser-proof-api", 8000), timeout, source_address)
    try:
        connection.request("GET", path, headers={"Authorization": "Bearer " + prefix + "." + signature})
        response = connection.getresponse()
        raw = response.read(128 * 1024 + 1)
        check(len(raw) <= 128 * 1024, "bounded own API response")
        status, body, headers = response.status, json.loads(raw), dict(response.getheaders())
    finally:
        connection.close()
    check(status == 200 and body["live_enabled"] is False and body["mode"] == "paper",
          "actual authenticated API assets")
    check("no-store" in next((v for k, v in headers.items() if k.lower() == "cache-control"), ""),
          "private asset response not cached")
    check(body["tenant_id"] == session["value"]["tenantId"] and len(body["accounts"]) == 1,
          "own tenant and account only")
    return body


def assets(session):
    return api_get(session, "/v1/futures-paper-assets")["accounts"][0]["snapshot"]


def run():
    global STAGE
    check(os.getenv("FUTURES_LOCAL_ACCEPTANCE_ENABLED") == "1" and os.geteuid() == 10003,
          "explicit nonroot local acceptance opt-in")
    fd = _directory(ROOT)
    try:
        marker = os.open(".fixture", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            info = os.fstat(marker)
            check(stat.S_ISREG(info.st_mode) and info.st_uid == 10003 and info.st_nlink == 1
                  and stat.S_IMODE(info.st_mode) == 0o400
                  and os.read(marker, 128) == b"synthetic-local-futures-acceptance/1\n",
                  "protected synthetic acceptance marker")
        finally:
            os.close(marker)
    finally:
        os.close(fd)
    actor = fixture()
    run_root = ROOT / uuid4().hex
    run_root.mkdir(mode=0o700)
    archive = run_root / "archive"
    archive.mkdir(mode=0o700)
    STAGE = "native contracts"
    # Raw evidence is preserved even if subsequent profile/worker checks fail.
    contract_receipt = capture_contracts(run_root / "contracts")
    rules = parse_contracts((run_root / "contracts/contracts.selected.json").read_bytes())
    now = datetime.now(timezone.utc)
    check(now.minute < 57, "bounded acceptance starts before hour rollover")
    config = local_config(str(actor["tenant"]), str(actor["account"]), rules,
                          contract_receipt["selected_sha256"],
                          now.replace(minute=0, second=0, microsecond=0))
    binding = PaperAccountBinding(str(actor["tenant"]), str(actor["account"]), str(actor["user"]),
                                  browser.ISSUER, actor["subject"], 0,
                                  datetime.fromtimestamp(actor["auth_time"], timezone.utc))
    spec = PaperBootstrapSpec(binding, config)
    spec_path = run_root / "allocation.json"
    spec_sha = save_spec(spec_path, spec)
    save(run_root, "economics.json", ASSUMPTIONS)
    journal_path = run_root / "paper.jsonl"
    arguments = ["--spec", str(spec_path), "--spec-digest", spec_sha,
                 "--journal", str(journal_path), "--archive-root", str(archive),
                 "--status-root", str(ROOT / "status"), "--cycles", "1"]
    runtime = {"PGUSER": "investalo_runtime", "PGPASSWORD_FILE": "/run/secrets/platform_runtime_password"}
    STAGE = "native initialization and quote publication"
    with patch.dict(os.environ, runtime):
        worker_main([*arguments, "--initialize"])
    published = FuturesAssetReader(ROOT / "status").publication(binding.tenant_id, binding.account_id)
    check(published is not None, "acknowledged own status published")
    with FuturesPaperJournal.restore(journal_path, config_digest=config.config_digest,
                                     minimum_receipt=published.journal_receipt) as journal:
        baseline = journal.state
        check(baseline.warmed and baseline.config.profile.plan.initial_equity == Decimal(10000),
              "explicit own allocation and native warmup")
        _, _, cursor = journal.source_checkpoint()
        check(cursor.warmup is not None and cursor.market is not None, "durable native source cursor")
        baseline_receipt = journal.receipt
    STAGE = "actual HTTPS Cockpit"
    session = browser.session(actor)
    status, _, _ = browser.request("/api/futures/settings", payload={
        "account_id": binding.account_id, "expected_revision": 0, "basket_limit": 3})
    check(status == 401, "unauthenticated BFF rejected")
    snapshot = assets(session)
    check(snapshot is not None and snapshot["data_fresh"] and snapshot["timeframe"] == "H1",
          "fresh native publication through authenticated HTTPS API")
    check(tuple(a["symbol"] for a in snapshot["assets"]) == SYMBOLS,
          "five actual native candidates")
    check(all(a["rsi"] is not None and 0 <= Decimal(a["rsi"]) <= 100 for a in snapshot["assets"]),
          "actual closed H1 Wilder RSI14")
    save(run_root, "assets-initial.json", snapshot)
    for path in ("/", "/portfolio"):
        status, html, _ = browser.request(path, session)
        check(status == 200 and "Handelsassets" in html and all(s in html for s in SYMBOLS)
              and "RSI-Kerzenschluss:" in html and "Nächster H1-Signalcheck:" in html,
              "actual Next SSR selected asset table")
        check("Der aktuelle Futures-Paperstand ist derzeit nicht verfügbar." not in html
              and "Der Futures-Paperzustand ist noch nicht angeschlossen." not in html,
              "strict TS contract accepts actual native snapshot")
        if path == "/portfolio":
            check("Kapitalempfehlung:" in html and "gleichzeitige Baskets" in html
                  and "Freie Mittel nach Reserven" in html, "actual SSR capacity recommendation")
    planned = api_get(session, "/v1/futures-paper-settings")["accounts"][0]
    check(planned["runtime_ready"] and planned["recommendation"] == 3
          and planned["capacity"]["funded_capacity"] == 3,
          "native current minimums and own cash recommend three funded ranges")
    status, settings, _ = browser.request("/api/futures/settings", session,
        {"account_id": binding.account_id, "expected_revision": 0, "basket_limit": 3})
    check(status == 200, "actual BFF settings CAS saved")
    check(settings["accounts"][0]["recommendation"] is None
          and settings["accounts"][0]["runtime_ready"] is False,
          "saved setting waits for acknowledged worker before recommendation")
    check(settings["accounts"][0]["recommendation_reason"] == "paper_settings_pending",
          "actual settings revision mismatch blocks stale advice")
    STAGE = "bound restart and setting application"
    with patch.dict(os.environ, runtime):
        worker_main(arguments)
    published = FuturesAssetReader(ROOT / "status").publication(binding.tenant_id, binding.account_id)
    with FuturesPaperJournal.restore(journal_path, config_digest=config.config_digest,
                                     minimum_receipt=published.journal_receipt) as journal:
        final_state, final_receipt = journal.state, journal.receipt
        check(final_state.settings_revision == 1
              and final_state.config.profile.plan.configured_limit == 3,
              "actual saved setting applied after CLI restart")
        check(final_state.config.profile.plan.budgets == baseline.config.profile.plan.budgets
              and final_state.config.profile.plan.initial_equity == Decimal(10000)
              and final_state.config.profile.plan.simultaneous_limit == 3,
              "restart preserves own full capital and funded capacity")
        check(final_receipt["sequence"] > baseline_receipt["sequence"],
              "full restored journal advanced without reset")
    restored_snapshot = assets(session)
    check(restored_snapshot["revision"] == final_state.revision, "API sees latest acknowledged restart")
    save(run_root, "assets-restored.json", restored_snapshot)
    planned = api_get(session, "/v1/futures-paper-settings")["accounts"][0]
    check(planned["runtime_ready"] and planned["recommendation"] == 3
          and planned["revision"] == 1, "restored own capacity follows actual saved setting")
    save(run_root, "capacity-restored.json", planned)
    with browser.admin() as db:
        rows = db.execute("SELECT revision,basket_limit,actor_id FROM platform.futures_paper_settings_audit "
                          "WHERE tenant_id=%s AND account_id=%s", (actor["tenant"], actor["account"])).fetchall()
        check(rows == [{"revision": 1, "basket_limit": 3, "actor_id": actor["user"]}],
              "exact own atomic settings audit")
    STAGE = "stale quote display"
    sleep(31)
    stale = assets(session)
    check(not stale["data_fresh"] and stale["observed_at"] == restored_snapshot["observed_at"]
          and all("data_stale" in a["next_buy"]["reasons"] for a in stale["assets"]),
          "read does not refresh actual quote clock")
    status, html, _ = browser.request("/", session)
    check(status == 200 and "Datenstand veraltet oder noch im Aufbau." in html,
          "actual SSR shows stale blocker")
    save(run_root, "assets-stale.json", stale)
    planned = api_get(session, "/v1/futures-paper-settings")["accounts"][0]
    check(planned["recommendation"] is None and not planned["runtime_ready"]
          and planned["recommendation_reason"] == "stale_instrument_data",
          "actual API refuses stale minimum/cash recommendation")
    STAGE = "revoked account blocks restart"
    before_hash = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    cohorts = tuple(sorted(archive.iterdir()))
    with browser.admin() as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                   (actor["tenant"], actor["account"]))
    rejected = False
    with patch.dict(os.environ, runtime):
        try:
            worker_main(arguments)
        except SystemExit as error:
            rejected = str(error) == (
                "Bound Paper stopped (PaperAccountRejected); readback/reconciliation required")
    check(rejected and hashlib.sha256(journal_path.read_bytes()).hexdigest() == before_hash
          and tuple(sorted(archive.iterdir())) == cohorts,
          "paused own account stops before source capture or journal change")
    paused = assets(session)
    check(all("account_unavailable" in a["next_buy"]["reasons"] for a in paused["assets"]),
          "API also shows current account pause")
    receipt = {
        "schema_version": "futures-local-cockpit-acceptance/1",
        "completed_at": datetime.now(timezone.utc).isoformat(), "checks": CHECKS,
        "allocation_digest": spec_sha, "configuration_digest": config.config_digest,
        "contract_receipt_sha256": hashlib.sha256(
            (run_root / "contracts/receipt.json").read_bytes()).hexdigest(),
        "initial_journal_receipt": baseline_receipt, "final_journal_receipt": final_receipt,
        "native_sources": True, "synthetic_identity": True, "synthetic_encrypted_session": True,
        "actual_https_bff_api_pg_ssr": True, "physical_browser_verified": False,
        "pause_before_http_verified": True,
        "current_capacity_verified": True,
        "initial_slots": 3, "initial_equity": "10000", "leverage": "2",
        "entries": len(final_state.signal.economic.stages),
        "closures": final_state.signal.economic.ledger.closed_baskets,
        "broker_admission_verified": False, "performance_evaluated": False,
        "public_enabled": False, "execution_enabled": False,
    }
    sha = save(run_root, "acceptance-receipt.json", receipt)
    print(f"PASS: {CHECKS} local native Futures/HTTPS/Cockpit checks; receipt {sha}; run {run_root.name}")


if __name__ == "__main__":
    os.umask(0o077)
    try:
        run()
    except BaseException as error:
        reason = str(error) if isinstance(error, browser.CheckFailure) else type(error).__name__
        raise SystemExit(f"Local Futures acceptance stopped at {STAGE} ({reason}); "
                         "preserve run; no success receipt; sensitive output suppressed") from None
