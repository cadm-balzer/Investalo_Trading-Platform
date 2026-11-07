"""Each authenticated operation owns one transaction and local tenant context."""
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from fastapi import HTTPException
import psycopg
from psycopg.rows import dict_row

from .auth import Assertion
from .settings import Settings


SCHEMA_VERSION = "002_research"


def connect(settings: Settings):
    return psycopg.connect(**settings.connection_parameters(), row_factory=dict_row)


def assert_runtime(connection) -> None:
    role = connection.execute(
        "SELECT current_user AS name, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
        "FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    if (
        not role or role["name"] != "investalo_runtime"
        or any(role[key] for key in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb"))
    ):
        raise HTTPException(503, "Service unavailable")


@contextmanager
def transaction(settings: Settings, identity: Assertion, *, tenant_required=True) -> Iterator:
    try:
        with connect(settings) as connection:
            assert_runtime(connection)
            connection.execute(
                "SELECT set_config('app.oidc_issuer', %s, true), "
                "set_config('app.oidc_subject', %s, true)",
                (identity.oidc_issuer, identity.subject),
            )
            user = connection.execute(
                "SELECT id, auth_epoch, reauth_after FROM platform.users "
                "WHERE oidc_issuer=%s AND oidc_subject=%s AND active",
                (identity.oidc_issuer, identity.subject),
            ).fetchone()
            if not user:
                raise HTTPException(403, "Access denied")
            if (
                datetime.fromtimestamp(identity.oidc_auth_time, timezone.utc) < user["reauth_after"]
                or identity.auth_epoch is not None and identity.auth_epoch != user["auth_epoch"]
            ):
                raise HTTPException(401, "Reauthentication required")
            connection.execute("SELECT set_config('app.user_id', %s, true)", (str(user["id"]),))
            if tenant_required:
                if identity.tenant_id is None:
                    raise HTTPException(403, "Tenant membership required")
                membership = connection.execute(
                    "SELECT role FROM platform.memberships "
                    "WHERE user_id=%s AND tenant_id=%s AND active",
                    (user["id"], identity.tenant_id),
                ).fetchone()
                if not membership:
                    raise HTTPException(403, "Access denied")
                connection.execute(
                    "SELECT set_config('app.tenant_id', %s, true)", (str(identity.tenant_id),),
                )
                user["role"] = membership["role"]
            # The PK provides cross-process replay protection, with no local-only cache.
            inserted = connection.execute(
                "INSERT INTO platform.request_nonces(jti,user_id,expires_at) "
                "VALUES (%s,%s,to_timestamp(%s)) ON CONFLICT DO NOTHING RETURNING jti",
                (identity.nonce, user["id"], identity.expires_at),
            ).fetchone()
            if not inserted:
                raise HTTPException(401, "Authentication required")
            yield connection, user
    except HTTPException:
        raise
    except psycopg.Error:
        # Connection strings, SQL, parameters and broker data never enter responses.
        raise HTTPException(503, "Service unavailable") from None
