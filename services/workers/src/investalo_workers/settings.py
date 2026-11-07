from dataclasses import dataclass, field
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class WorkerSettings:
    parameters: dict = field(repr=False)

    @classmethod
    def from_environment(cls):
        if os.getenv("PGSSLMODE") != "verify-full":
            raise ValueError("Research worker requires verified database TLS")
        if not os.getenv("PGPASSWORD_FILE") or not os.getenv("PGUSER"):
            raise ValueError("Dedicated research database identity required")
        password = Path(os.environ["PGPASSWORD_FILE"]).read_text().rstrip("\r\n")
        if not password:
            raise ValueError("Research credential unavailable")
        values = {
            parameter: os.environ[variable]
            for variable, parameter in (
                ("PGHOST", "host"), ("PGPORT", "port"), ("PGDATABASE", "dbname"),
                ("PGUSER", "user"), ("PGSSLMODE", "sslmode"),
                ("PGSSLROOTCERT", "sslrootcert"),
            ) if variable in os.environ
        }
        return cls({**values, "password": password, "connect_timeout": 3})

    def connect(self):
        return psycopg.connect(
            **self.parameters, row_factory=dict_row,
            options="-c statement_timeout=5000 -c lock_timeout=3000",
        )


def assert_research_identity(db):
    role = db.execute(
        "SELECT r.rolsuper,r.rolbypassrls,r.rolcreaterole,r.rolcreatedb,"
        "current_user=session_user AS direct_login,"
        "pg_has_role(session_user,'investalo_research_worker','MEMBER') AS research_member "
        "FROM pg_roles r WHERE r.rolname=session_user"
    ).fetchone()
    if (
        not role or not role["direct_login"] or not role["research_member"]
        or any(role[name] for name in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb"))
    ):
        raise ValueError("Unsafe research identity")
    bound = db.execute("SELECT platform.research_tenant() AS tenant_id").fetchone()["tenant_id"]
    if bound is None:
        raise ValueError("Research identity is not tenant-bound")
    return bound
