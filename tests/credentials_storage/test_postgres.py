"""Real PostgreSQL authorization, AEAD-record persistence and concurrency gates."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import secrets
from threading import Barrier
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from investalo_credentials import AADBinding, KEKRing, SecretPayload, dump_envelope, load_envelope, open_envelope, rewrap, seal
from conftest import connect_as

FIELDS = ("tenant_id", "user_id", "platform_account_id", "connection_id", "broker_uid", "parent_uid",
          "broker", "account_family", "connection_mode", "credential_revision", "storage_version", "status", "envelope")


def binding(context, connection_id, uid, *, who="a", revision=1, parent=None, account=None):
    return AADBinding(
        tenant_id=context[f"tenant_{who}"], user_id=context[f"user_{who}"],
        platform_account_id=account or context[f"account_{who}"], connection_id=connection_id,
        broker_uid=uid, parent_uid=parent, credential_revision=revision,
    )


def wire(bound, *, keyring=None):
    keyring = keyring or KEKRing((("synthetic-v1", secrets.token_bytes(32)),), active_version="synthetic-v1")
    return json.loads(dump_envelope(seal(SecretPayload(b"synthetic-only-test-payload"), bound, keyring))), keyring


def create(context, *, who="a", uid=None, parent=None, account=None, connection_id=None):
    connection_id, uid = connection_id or uuid4(), uid or str(secrets.randbelow(10**18) + 1)
    account = account or context[f"account_{who}"]
    bound = binding(context, connection_id, uid, who=who, parent=parent, account=account)
    envelope, ring = wire(bound)
    with connect_as(who) as database:
        row = database.execute(
            "SELECT * FROM platform.credential_create(%s,%s,%s,%s,%s)",
            (account, connection_id, uid, parent, Jsonb(envelope)),
        ).fetchone()
    return row, bound, ring


def operation(context, row, name, *, who="a", envelope=None, revision=None, storage=None):
    arguments = (row["connection_id"], row["credential_revision"] if revision is None else revision,
                 row["storage_version"] if storage is None else storage)
    if name == "revoke":
        with connect_as(who) as database:
            return database.execute(
                "SELECT platform.credential_revoke(%s,%s,%s) AS storage_version", arguments,
            ).fetchone()["storage_version"]
    if name not in ("replace", "rewrap"):
        raise ValueError("Unknown synthetic test operation")
    statement = sql.SQL("SELECT * FROM platform.{}(%s,%s,%s,%s)").format(sql.Identifier("credential_" + name))
    with connect_as(who) as database:
        return database.execute(statement, (*arguments, Jsonb(row["envelope"] if envelope is None else envelope))).fetchone()


def denied(operation):
    with pytest.raises(psycopg.errors.InsufficientPrivilege) as failure:
        operation()
    assert failure.value.sqlstate == "42501"


def test_session_identity_ignores_tenant_owner_gucs_and_group_set_role(credential_database):
    context = credential_database
    with connect_as("a") as database:
        database.execute("SELECT set_config('app.tenant_id',%s,true)", (str(context["tenant_b"]),))
        database.execute("SELECT set_config('app.user_id',%s,true)", (str(context["user_b"]),))
        database.execute("SET LOCAL ROLE investalo_credentials_worker")
        identity = database.execute("SELECT * FROM platform.credential_context()").fetchone()
        assert identity == {"tenant_id": context["tenant_a"], "user_id": context["user_a"]}
    with connect_as("unbound") as database:
        denied(lambda: database.execute("SELECT * FROM platform.credential_context()"))
    with connect_as("a") as database:
        denied(lambda: database.execute("SET SESSION AUTHORIZATION investalo_migration"))


def test_record_contains_authoritative_immutable_aad_and_ciphertext_only(credential_database):
    row, bound, ring = create(credential_database, parent="0")
    assert tuple(row) == FIELDS
    assert row["status"] == "active" and row["credential_revision"] == row["storage_version"] == 1
    assert row["parent_uid"] == "0"
    assert "synthetic-only-test-payload" not in json.dumps(row["envelope"])
    with connect_as("a") as database:
        stored = database.execute("SELECT * FROM platform.credential_read(%s)", (row["connection_id"],)).fetchone()
    assert stored == row
    assert open_envelope(load_envelope(json.dumps(stored["envelope"])), bound, ring).reveal() == b"synthetic-only-test-payload"


def test_connections_are_user_owned_even_within_same_tenant(credential_database):
    context = credential_database
    row, *_ = create(context)
    with connect_as("b") as database:
        denied(lambda: database.execute("SELECT * FROM platform.credential_read(%s)", (row["connection_id"],)))
    denied(lambda: create(context, who="b", account=context["account_a"]))
    with connect_as("admin") as database:
        database.execute(
            "UPDATE platform.credential_role_bindings SET tenant_id=%s WHERE database_role=%s",
            (context["tenant_a"], os.environ["CREDENTIAL_TEST_USER_B"]),
        )
    for name in ("replace", "rewrap", "revoke"):
        denied(lambda name=name: operation(context, row, name, who="b"))
    with connect_as("b") as database:
        denied(lambda: database.execute("SELECT * FROM platform.credential_read(%s)", (row["connection_id"],)))
    trader_context = {**context, "tenant_b": context["tenant_a"]}
    trader_row, *_ = create(trader_context, who="b", account=context["account_a2"])
    assert trader_row["tenant_id"] == context["tenant_a"] and trader_row["user_id"] == context["user_b"]
    with connect_as("a") as database:
        denied(lambda: database.execute("SELECT * FROM platform.credential_read(%s)", (trader_row["connection_id"],)))


def test_global_uid_unique_is_atomic_and_parent_aliases_cannot_bypass(credential_database):
    context = credential_database
    uid, barrier = str(secrets.randbelow(10**18) + 1), Barrier(2)
    def contender(who, parent):
        barrier.wait(timeout=5)
        try:
            create(context, who=who, uid=uid, parent=parent)
            return "created"
        except psycopg.errors.UniqueViolation as failure:
            assert failure.diag.message_primary == "identity_conflict"
            assert failure.diag.message_detail is None
            return failure.sqlstate
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(contender, "a", None)
        second = pool.submit(contender, "b", "0")
        assert sorted([first.result(timeout=15), second.result(timeout=15)]) == ["23505", "created"]
    with connect_as("admin") as database:
        count = database.execute("SELECT count(*) AS n FROM platform.credential_connections WHERE broker_uid=%s", (uid,)).fetchone()["n"]
    assert count == 1


def test_account_unique_foreign_key_and_live_readonly_gate(credential_database):
    context = credential_database
    row, *_ = create(context)
    with pytest.raises(psycopg.errors.UniqueViolation):
        create(context)  # Different UID, same platform account.
    with connect_as("admin") as database:
        columns = "tenant_id,user_id,platform_account_id,connection_id,broker_uid,credential_revision,storage_version,status,envelope"
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            database.execute(
                f"INSERT INTO platform.credential_connections({columns}) VALUES(%s,%s,%s,%s,%s,1,1,'active',%s)",
                (context["tenant_a"], context["user_a"], context["account_b"], uuid4(), str(secrets.randbelow(10**18)+1), Jsonb(row["envelope"])),
            )
    for change in ("mode='paper'", "broker='mt5'", "status='paused'"):
        with connect_as("admin") as database:
            database.execute(f"UPDATE platform.accounts SET {change} WHERE tenant_id=%s AND id=%s", (context["tenant_a"], context["account_a"]))
        with connect_as("a") as database:
            denied(lambda: database.execute("SELECT * FROM platform.credential_read(%s)", (row["connection_id"],)))
        for name in ("replace", "rewrap"):
            denied(lambda name=name: operation(context, row, name))
        with connect_as("admin") as database:
            database.execute("UPDATE platform.accounts SET broker='bitget',mode='read_only',status='disconnected' WHERE tenant_id=%s AND id=%s",
                             (context["tenant_a"], context["account_a"]))
    with connect_as("admin") as database:
        database.execute("UPDATE platform.accounts SET mode='paper' WHERE tenant_id=%s AND id=%s", (context["tenant_a"], context["account_a2"]))
    denied(lambda: create(context, account=context["account_a2"]))


def test_replacement_and_rewrap_have_separate_monotonic_versions_and_cas(credential_database):
    context = credential_database
    row, original_binding, ring = create(context)
    v2binding = binding(context, row["connection_id"], row["broker_uid"], revision=2)
    replacement, _ = wire(v2binding, keyring=ring)
    updated = operation(context, row, "replace", envelope=replacement)
    assert updated["credential_revision"] == 2 and updated["storage_version"] == 2
    assert open_envelope(load_envelope(json.dumps(updated["envelope"])), v2binding, ring).reveal() == b"synthetic-only-test-payload"
    for name in ("replace", "rewrap", "revoke"):
        with pytest.raises(psycopg.errors.SerializationFailure) as failure:
            operation(context, row, name)
        assert failure.value.diag.message_primary == "concurrent_change"
        assert failure.value.diag.message_detail is None
    rotated_ring = KEKRing((("synthetic-v1", ring._key("synthetic-v1")), ("synthetic-v2", secrets.token_bytes(32))), active_version="synthetic-v2")
    rotated = json.loads(dump_envelope(rewrap(load_envelope(json.dumps(updated["envelope"])), v2binding, rotated_ring)))
    rewrapped = operation(context, updated, "rewrap", envelope=rotated)
    assert rewrapped["credential_revision"] == 2 and rewrapped["storage_version"] == 3
    assert rewrapped["envelope"]["ciphertext"] == updated["envelope"]["ciphertext"]
    assert rewrapped["envelope"]["payload_nonce"] == updated["envelope"]["payload_nonce"]
    assert open_envelope(load_envelope(json.dumps(rewrapped["envelope"])), v2binding, rotated_ring).reveal() == b"synthetic-only-test-payload"
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        operation(context, rewrapped, "rewrap", envelope=row["envelope"])
    # Old envelope is still cryptographically valid only with its old AAD,
    # but the database never silently restores its stale revision/storage cursor.
    assert open_envelope(load_envelope(json.dumps(row["envelope"])), original_binding, ring).reveal()


def test_concurrent_cas_has_exactly_one_winner(credential_database):
    context = credential_database
    row, *_ = create(context)
    barrier = Barrier(2)
    def contender():
        barrier.wait(timeout=5)
        try:
            return operation(context, row, "rewrap")["storage_version"]
        except psycopg.errors.SerializationFailure as failure:
            return failure.sqlstate
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(contender), pool.submit(contender)
        assert sorted([str(first.result(timeout=15)), str(second.result(timeout=15))]) == ["2", "40001"]


def test_revocation_is_terminal_keeps_uid_and_works_with_paused_account(credential_database):
    context = credential_database
    row, *_ = create(context)
    with connect_as("admin") as database:
        database.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s", (context["tenant_a"], context["account_a"]))
    assert operation(context, row, "revoke") == 2
    for name in ("replace", "rewrap", "revoke"):
        denied(lambda name=name: operation(context, row, name))
    with connect_as("a") as database:
        denied(lambda: database.execute("SELECT * FROM platform.credential_read(%s)", (row["connection_id"],)))
    with pytest.raises(psycopg.errors.UniqueViolation):
        create(context, who="b", uid=row["broker_uid"])
    with connect_as("admin") as database:
        stored = database.execute("SELECT * FROM platform.credential_connections WHERE connection_id=%s", (row["connection_id"],)).fetchone()
        assert stored["status"] == "revoked" and stored["credential_revision"] == 1 and stored["storage_version"] == 2
        assert stored["envelope"] == row["envelope"]
    for mutation in ("status='active'", "user_id=user_id", "storage_version=storage_version+1"):
        with connect_as("admin") as database:
            denied(lambda: database.execute(f"UPDATE platform.credential_connections SET {mutation} WHERE connection_id=%s", (row["connection_id"],)))


@pytest.mark.parametrize("change", ["user_inactive", "membership_inactive", "viewer", "researcher"])
def test_current_user_and_membership_role_rechecked_for_every_operation(credential_database, change):
    context = credential_database
    row, *_ = create(context)
    with connect_as("admin") as database:
        if change == "user_inactive":
            database.execute("UPDATE platform.users SET active=false WHERE id=%s", (context["user_a"],))
        elif change == "membership_inactive":
            database.execute("UPDATE platform.memberships SET active=false WHERE tenant_id=%s AND user_id=%s", (context["tenant_a"], context["user_a"]))
        else:
            database.execute("UPDATE platform.memberships SET role=%s WHERE tenant_id=%s AND user_id=%s", (change, context["tenant_a"], context["user_a"]))
    for name in ("replace", "rewrap", "revoke"):
        denied(lambda name=name: operation(context, row, name))
    denied(lambda: create(context, account=context["account_a2"]))
    with connect_as("a") as database:
        denied(lambda: database.execute("SELECT * FROM platform.credential_read(%s)", (row["connection_id"],)))
    with connect_as("a") as database:
        denied(lambda: database.execute("SELECT * FROM platform.credential_context()"))


def test_ciphertext_and_binding_tables_and_helpers_are_not_runtime_capabilities(credential_database):
    row, *_ = create(credential_database)
    for who in ("a", "runtime", "research"):
        for table in ("credential_connections", "credential_role_bindings"):
            with connect_as(who) as database:
                denied(lambda: database.execute(sql.SQL("SELECT * FROM platform.{}").format(sql.Identifier(table))))
            with connect_as(who) as database:
                denied(lambda: database.execute(sql.SQL("UPDATE platform.{} SET tenant_id=tenant_id").format(sql.Identifier(table))))
        for call in ("platform.credential_owned(NULL)", "platform.credential_envelope_valid('{}')"):
            with connect_as(who) as database:
                denied(lambda: database.execute("SELECT " + call))
    for who in ("runtime", "research"):
        for call in (
            "platform.credential_context()", "platform.credential_read(NULL)",
            "platform.credential_create(NULL,NULL,NULL,NULL,'{}')",
            "platform.credential_replace(NULL,1,1,'{}')", "platform.credential_rewrap(NULL,1,1,'{}')",
            "platform.credential_revoke(NULL,1,1)",
        ):
            with connect_as(who) as database:
                denied(lambda: database.execute("SELECT * FROM " + call))
    for statement in ("DELETE FROM platform.credential_connections", "TRUNCATE platform.credential_connections",
                      "ALTER TABLE platform.credential_connections DISABLE ROW LEVEL SECURITY"):
        with connect_as("a") as database:
            denied(lambda: database.execute(statement))
    assert row["envelope"]


def test_immutable_binding_and_counter_guards_apply_even_to_migration_owner(credential_database):
    context = credential_database
    row, *_ = create(context)
    changes = (
        sql.SQL("broker_uid='123456789'"), sql.SQL("parent_uid='0'"),
        sql.SQL("user_id={}").format(sql.Literal(context["user_b"])),
        sql.SQL("platform_account_id={}").format(sql.Literal(context["account_a2"])),
        sql.SQL("credential_revision=0"), sql.SQL("credential_revision=3"),
    )
    for change in changes:
        with connect_as("admin") as database:
            denied(lambda: database.execute(
                sql.SQL("UPDATE platform.credential_connections SET {},storage_version=storage_version+1 WHERE connection_id=%s").format(change),
                (row["connection_id"],),
            ))
    with connect_as("admin") as database:
        denied(lambda: database.execute(
            "UPDATE platform.credential_connections SET storage_version=storage_version WHERE connection_id=%s",
            (row["connection_id"],),
        ))
    for statement in ("DELETE FROM platform.credential_connections WHERE connection_id=%s",
                      "TRUNCATE platform.credential_connections"):
        with connect_as("admin") as database:
            denied(lambda: database.execute(statement, (row["connection_id"],) if "%s" in statement else None))


def test_envelope_shape_is_bounded_exact_and_never_accepts_plaintext_fields(credential_database):
    context = credential_database
    row, *_ = create(context)
    base = row["envelope"]
    patches = (
        {**base, "plaintext": "synthetic-only-secret"}, {key: value for key, value in base.items() if key != "kek_id"},
        {**base, "schema_version": "unknown/2"}, {**base, "kek_id": "x"*65}, {**base, "kek_id": "../key"},
        {**base, "ciphertext": "A"*9000}, {**base, "payload_nonce": "A"*15},
        {**base, "wrap_nonce": None}, {**base, "wrapped_dek": "A"*63},
        {**base, "ciphertext": "AAAA"}, {**base, "ciphertext": 1},
        {**base, "ciphertext": "not-base64"}, [],
    )
    for envelope in patches:
        with pytest.raises(psycopg.errors.InvalidParameterValue) as failure:
            operation(context, row, "replace", envelope=envelope)
        assert failure.value.diag.message_primary == "invalid_record"
        assert failure.value.diag.message_detail is None
    with connect_as("a") as database:
        assert database.execute("SELECT * FROM platform.credential_read(%s)", (row["connection_id"],)).fetchone() == row


def test_rls_definer_ownership_fixed_search_path_and_function_acl(credential_database):
    with connect_as("admin") as database:
        tables = database.execute(
            "SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='platform' "
            "AND c.relname IN ('credential_connections','credential_role_bindings')",
        ).fetchall()
        assert len(tables) == 2 and all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in tables)
        functions = database.execute(
            "SELECT p.proname,p.prosecdef,p.proconfig,pg_get_userbyid(p.proowner) AS owner "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='platform' AND p.proname LIKE 'credential_%'",
        ).fetchall()
        assert len(functions) == 8
        for function in functions:
            assert function["owner"] == "investalo_migration"
            assert function["proconfig"] == ["search_path=pg_catalog"]
            assert function["prosecdef"] == (function["proname"] != "credential_envelope_valid")
        assert database.execute(
            "SELECT count(*) AS n FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='platform' "
            "AND c.relname IN ('credential_connections','credential_role_bindings')",
        ).fetchone()["n"] == 2
    with connect_as("a") as database:
        role = database.execute(
            "SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication "
            "FROM pg_roles WHERE rolname=SESSION_USER",
        ).fetchone()
        assert role == {"rolcanlogin": True, "rolsuper": False, "rolbypassrls": False,
                        "rolcreaterole": False, "rolcreatedb": False, "rolreplication": False}
