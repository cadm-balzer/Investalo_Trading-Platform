"""Isolated PostgreSQL fixtures; root provisions dedicated synthetic LOGINs."""
from contextlib import contextmanager
from pathlib import Path
import os
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
import pytest

IDENTITIES = {
    "admin": ("API_TEST_ADMIN_USER", "API_TEST_ADMIN_PASSWORD_FILE"),
    "runtime": ("PGUSER", "PGPASSWORD_FILE"),
    "research": ("API_TEST_RESEARCH_USER", "API_TEST_RESEARCH_PASSWORD_FILE"),
    "a": ("CREDENTIAL_TEST_USER_A", "CREDENTIAL_TEST_PASSWORD_A_FILE"),
    "b": ("CREDENTIAL_TEST_USER_B", "CREDENTIAL_TEST_PASSWORD_B_FILE"),
    "unbound": ("CREDENTIAL_TEST_USER_UNBOUND", "CREDENTIAL_TEST_PASSWORD_UNBOUND_FILE"),
}


@contextmanager
def connect_as(identity, *, tuple_rows=False):
    user_variable, password_variable = IDENTITIES[identity]
    # The mounted password is consumed inside the test container only; neither
    # fixture objects nor public exception chains retain its connection mapping.
    try:
        password = Path(os.environ[password_variable]).read_text().strip()
        if not password or len(password) > 16384:
            raise ValueError()
        parameters = dict(
            host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")),
            dbname=os.environ["PGDATABASE"], user=os.environ[user_variable],
            password=password, sslmode=os.environ.get("PGSSLMODE", "verify-full"),
            sslrootcert=os.environ["PGSSLROOTCERT"], connect_timeout=5,
        )
        if not tuple_rows:
            parameters["row_factory"] = dict_row
        database = psycopg.connect(**parameters)
    except Exception:
        raise RuntimeError("Isolated PostgreSQL test connection unavailable") from None
    with database:
        database.execute("SET LOCAL statement_timeout='10s'")
        database.execute("SET LOCAL lock_timeout='5s'")
        yield database


@pytest.fixture
def credential_database():
    required = {"PGHOST", "PGDATABASE", "PGSSLROOTCERT"}
    for identity in IDENTITIES.values():
        required.update(identity)
    if any(not os.getenv(variable) for variable in required):
        pytest.skip("Requires isolated credential test LOGINs and administrative fixture identity")
    context = {key: uuid4() for key in ("tenant_a", "tenant_b", "user_a", "user_b", "account_a", "account_a2", "account_b")}
    with connect_as("admin") as database:
        database.execute(
            "INSERT INTO platform.tenants(id,name) VALUES(%s,'Synthetic credential A'),(%s,'Synthetic credential B')",
            (context["tenant_a"], context["tenant_b"]),
        )
        for suffix in ("a", "b"):
            database.execute(
                "INSERT INTO platform.users(id,oidc_issuer,oidc_subject) VALUES(%s,'https://credential-test.invalid',%s)",
                (context[f"user_{suffix}"], "synthetic-" + uuid4().hex),
            )
            database.execute(
                "INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'owner')",
                (context[f"tenant_{suffix}"], context[f"user_{suffix}"]),
            )
        database.execute(
            "INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'trader')",
            (context["tenant_a"], context["user_b"]),
        )
        for key, tenant in (("account_a", "tenant_a"), ("account_a2", "tenant_a"), ("account_b", "tenant_b")):
            database.execute(
                "INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency) "
                "VALUES(%s,%s,'Synthetic read-only account','bitget','read_only','USDT')",
                (context[tenant], context[key]),
            )
        for suffix in ("a", "b"):
            database.execute(
                "INSERT INTO platform.credential_role_bindings(database_role,tenant_id,user_id) VALUES(%s,%s,%s) "
                "ON CONFLICT(database_role) DO UPDATE SET tenant_id=excluded.tenant_id,user_id=excluded.user_id",
                (os.environ[f"CREDENTIAL_TEST_USER_{suffix.upper()}"], context[f"tenant_{suffix}"], context[f"user_{suffix}"]),
            )
        # Never mutate live credentials or research bindings. Dedicated test
        # binding rows may be reassigned; append-only test connections remain.
        assert database.execute(
            "SELECT 1 FROM platform.credential_role_bindings WHERE database_role=%s",
            (os.environ["CREDENTIAL_TEST_USER_UNBOUND"],),
        ).fetchone() is None
    return context
