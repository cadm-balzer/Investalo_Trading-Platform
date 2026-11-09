"""Explicit bounded development observation, never a production/broker launcher."""
from contextlib import contextmanager
import hashlib
import os

ROLE = "investalo_paper_development"
DATABASE = "investalo_credentials_checks"
MAX_SECONDS = 86400
MAX_FAILURES = 6


class PaperLeaseLost(RuntimeError):
    pass


def require_development():
    expected = {
        "PGHOST": "postgres", "PGPORT": "5432", "PGDATABASE": DATABASE,
        "PGUSER": ROLE, "PGSSLMODE": "verify-full",
        "PGSSLROOTCERT": "/run/secrets/local_ca_cert",
        "PGPASSWORD_FILE": "/run/secrets/paper_development_password",
    }
    if (os.getenv("PAPER_DEVELOPMENT_MODE") != "1"
            or os.getenv("PAPER_WORKER_ENABLED") != "1"
            or any(os.getenv(key) != value for key, value in expected.items())
            or any(key.startswith("PG") and key not in expected for key in os.environ)):
        raise ValueError("Paper development environment rejected")


def lock_key(tenant, account):
    value = f"investalo-paper-development/1:{tenant}:{account}".encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big") & ((1 << 63)-1)


def identity(db):
    row = db.execute(
        "SELECT current_database() AS database,current_user AS current,session_user AS session,"
        "rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication FROM pg_roles"
        " WHERE rolname=session_user").fetchone()
    if (not row or row["database"] != DATABASE or row["current"] != ROLE or row["session"] != ROLE
            or any(row[k] for k in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication"))):
        raise ValueError("Paper development identity rejected")


@contextmanager
def singleton(worker):
    db = None
    try:
        db = worker.store.connect()
        db.autocommit = True
        identity(db)
        key = lock_key(worker.runner.tenant_id, worker.runner.account_id)
        if not db.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (key,)).fetchone()["acquired"]:
            raise ValueError("Paper development instance already active")

        def heartbeat():
            try:
                identity(db)
                row = db.execute(
                    "SELECT EXISTS(SELECT FROM pg_locks WHERE pid=pg_backend_pid()"
                    " AND locktype='advisory' AND granted AND objsubid=1"
                    " AND classid::bigint=((%s::bigint >> 32) & 4294967295)"
                    " AND objid::bigint=(%s::bigint & 4294967295)) AS held", (key, key)).fetchone()
                if not row["held"]:
                    raise ValueError()
            except Exception:
                raise PaperLeaseLost("Paper development instance lock lost") from None
        heartbeat()
        yield heartbeat
    finally:
        if db is not None:
            try:
                db.close()  # Session end releases advisory lock, including abnormal exits.
            except Exception:
                pass
