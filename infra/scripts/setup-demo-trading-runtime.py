#!/usr/bin/env python3
"""Prepare the operative private Demo installation; never reads a broker key.

Default: create-only files, no DB change/service start. --bind-account is a
separate rollout step after migration019 and deployment approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from uuid import UUID, uuid4

REPO = Path(__file__).resolve().parents[2]
LOCAL = REPO / "infra/local"
ROOT = LOCAL / "demo-trading-runtime"
LOGIN = "investalo_demo_trading_credential"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def private(path, uid=0, limit=8192, mode=0o400):
    # Reject symlinks in every component; setup files are original, private,
    # single-link regular files. Never print their content on failure.
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError()
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != uid
            or stat.S_IMODE(metadata.st_mode) != mode or metadata.st_nlink != 1
            or not 1 <= metadata.st_size <= limit):
        raise ValueError()
    return path.read_bytes()


def write(path, value, uid):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
        os.fchown(stream.fileno(), uid, uid)


def wire(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def sql(command):
    result = subprocess.run(["bash", str(REPO / "infra/scripts/compose.sh"),
        "exec", "-T", "postgres", "psql", "--no-psqlrc", "--username", "investalo_admin",
        "--dbname", "investalo", "--tuples-only", "--no-align", "--set", "ON_ERROR_STOP=1"],
        input=command, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError()
    return result.stdout.strip()


def tls(directory, name, hostname, purpose):
    def openssl(*args):
        subprocess.run(["openssl", *args], cwd=directory, check=True,
                       capture_output=True, timeout=15)
    openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256", "-out", name + ".key")
    openssl("req", "-new", "-key", name + ".key", "-subj", "/CN=" + hostname, "-out", name + ".csr")
    (directory / (name + ".ext")).write_text(
        "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n"
        "extendedKeyUsage=" + purpose + "\nsubjectAltName=DNS:" + hostname + "\n")
    openssl("x509", "-req", "-in", name + ".csr", "-CA", "ca.crt", "-CAkey", "ca.key",
            "-set_serial", str(secrets.randbits(128) or 1), "-days", "365", "-sha256",
            "-extfile", name + ".ext", "-out", name + ".crt")
    return (directory / (name + ".crt")).read_bytes(), (directory / (name + ".key")).read_bytes()


def prepare(args):
    if (args.created_in_demo_mode is not True or not re.fullmatch("[1-9][0-9]{0,19}", args.broker_uid or "")
            or not re.fullmatch("0|[1-9][0-9]{0,19}", args.parent_uid)):
        raise ValueError()
    import ipaddress
    if str(ipaddress.ip_address(args.egress_ip)) != args.egress_ip:
        raise ValueError()
    # This manifest was installed by the existing public-preview provisioning.
    actor = json.loads(private(LOCAL / "public-preview-identity.json", limit=8192, mode=0o600))
    if actor["issuer"] != "https://auth.cockpit.investalo.de":
        raise ValueError()
    tenant, user = str(UUID(actor["tenant_id"])), str(UUID(actor["user_id"]))
    if sql(f"""SELECT count(*) FROM platform.users u JOIN platform.memberships m ON m.user_id=u.id
      WHERE u.id='{user}' AND m.tenant_id='{tenant}' AND u.active AND m.active AND m.role='owner'
      AND u.oidc_issuer='https://auth.cockpit.investalo.de';""") != "1":
        raise ValueError()
    for parent in (ROOT, *ROOT.parents):
        if parent.is_symlink():
            raise ValueError()
    ROOT.mkdir(mode=0o711)  # Never replace an existing KEK/identity/account.
    browser, executor = ROOT / "browser", ROOT / "executor"
    for location, uid in ((browser, 10002), (executor, 10003)):
        location.mkdir(mode=0o700)
        os.chown(location, uid, uid)
    material = ROOT / "authority"
    material.mkdir(mode=0o700)
    subprocess.run(["openssl", "req", "-new", "-x509", "-newkey", "ec",
        "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-sha256", "-days", "1095",
        "-subj", "/CN=Investalo Demo Trading Private CA",
        "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        "-keyout", str(material / "ca.key"), "-out", str(material / "ca.crt")],
        check=True, capture_output=True, timeout=15)
    client_cert, client_key = tls(material, "client", "cockpit.demo-trading.internal", "clientAuth")
    server_cert, server_key = tls(material, "server", "demo-trading-executor.cockpit.internal", "serverAuth")
    ca = (material / "ca.crt").read_bytes()
    client_der = subprocess.run(["openssl", "x509", "-in", str(material / "client.crt"),
        "-outform", "DER"], check=True, capture_output=True, timeout=15).stdout
    signing, kek = secrets.token_bytes(32), secrets.token_bytes(32)
    account = str(uuid4())
    # Existing authority fingerprints are private server input, never browser data.
    excluded = []
    for name in ("cockpit_session_key", "internal_api_key"):
        path = LOCAL / name
        if path.is_symlink() or not path.is_file():
            raise ValueError()
        excluded.append(sha(path.read_bytes().strip()))
    excluded.append(sha(kek))
    if len(set(excluded + [sha(signing)])) != 4:
        raise ValueError()
    browser_config = dict(schema="investalo-demo-trading-credential-private-identity/1",
        directory="/run/demo-trading-identity", ownerUid=10002, tenantId=tenant,
        userId=user, accountId=account, origin="https://cockpit.investalo.de",
        oidcIssuer="https://auth.cockpit.investalo.de",
        executorOrigin="https://demo-trading-executor.cockpit.internal:9443",
        signingSha256=sha(signing), caSha256=sha(ca), certificateSha256=sha(client_cert),
        privateKeySha256=sha(client_key), excludedSigningSha256=excluded)
    executor_config = dict(schema="investalo-demo-trading-runtime/1",
        tenant_id=tenant, user_id=user, account_id=account,
        broker_uid=args.broker_uid, parent_uid=args.parent_uid, egress_ip=args.egress_ip,
        ip_binding="unavailable_in_demo" if args.demo_without_ip_binding else "single_ip",
        origin=browser_config["origin"], oidc_issuer=browser_config["oidcIssuer"],
        created_in_bitget_demo_mode=True, signing_sha256=sha(signing),
        kek_sha256=sha(kek), client_certificate_sha256=sha(client_der))
    for name, value in (("config", wire(browser_config)), ("signing-key", signing),
                        ("executor-ca", ca), ("client-certificate", client_cert), ("client-private-key", client_key)):
        write(browser / name, value, 10002)
    for name, value in (("config", wire(executor_config)), ("signing-key", signing), ("kek", kek),
            ("database-password", secrets.token_urlsafe(48).encode()), ("client-ca", ca),
            ("tls-certificate", server_cert), ("tls-private-key", server_key)):
        write(executor / name, value, 10003)
    for path in material.iterdir():
        path.chmod(0o400)
    write(ROOT / "prepared", b"investalo-demo-trading-runtime-prepared/1\n", 0)
    print("Private Demo runtime prepared. Database and running services unchanged.")


def bind():
    private(ROOT / "prepared")
    config = json.loads(private(ROOT / "executor/config", 10003))
    password = private(ROOT / "executor/database-password", 10003).decode("ascii")
    tenant, user, account = (str(UUID(config[name])) for name in ("tenant_id", "user_id", "account_id"))
    if not re.fullmatch("[A-Za-z0-9_-]{64}", password):
        raise ValueError()
    # All original migrations must be present with their original checksums.
    expected = "\n".join(f"{path.stem}|{sha(path.read_bytes())}"
                        for path in sorted((REPO / "services/api/migrations").glob("*.sql")))
    if sql("SELECT version,checksum FROM platform.schema_migrations ORDER BY version;") != expected:
        raise ValueError()
    # Idempotent exact account/role binding, never adopts or resets another one.
    sql(f"""
BEGIN;
SELECT pg_catalog.pg_advisory_xact_lock(1380275026,3);
DO $$
BEGIN
 IF NOT EXISTS(SELECT FROM platform.users u JOIN platform.memberships m ON m.user_id=u.id
  WHERE u.id='{user}' AND m.tenant_id='{tenant}' AND u.active AND m.active AND m.role='owner'
  AND u.oidc_issuer='https://auth.cockpit.investalo.de') THEN RAISE EXCEPTION 'actor'; END IF;
 IF EXISTS(SELECT FROM pg_catalog.pg_roles WHERE rolname='{LOGIN}') THEN
  IF NOT EXISTS(SELECT FROM platform.credential_role_bindings
    WHERE database_role='{LOGIN}' AND tenant_id='{tenant}' AND user_id='{user}') THEN
    RAISE EXCEPTION 'existing role'; END IF;
 ELSE
  CREATE ROLE {LOGIN} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    PASSWORD '{password}';
  GRANT investalo_credentials_worker TO {LOGIN};
  INSERT INTO platform.credential_role_bindings(database_role,tenant_id,user_id)
    VALUES('{LOGIN}','{tenant}','{user}');
 END IF;
 IF NOT EXISTS(SELECT FROM platform.accounts WHERE tenant_id='{tenant}' AND id='{account}') THEN
  INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)
    VALUES('{tenant}','{account}','Bitget Demo','bitget','bitget_demo','USDT','ready');
 ELSIF NOT EXISTS(SELECT FROM platform.accounts WHERE tenant_id='{tenant}' AND id='{account}'
   AND broker='bitget' AND mode='bitget_demo' AND currency='USDT') THEN
   RAISE EXCEPTION 'existing account'; END IF;
 IF EXISTS(SELECT FROM pg_catalog.pg_roles WHERE rolname='{LOGIN}'
   AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
        OR NOT rolcanlogin OR NOT rolinherit))
   OR NOT pg_catalog.pg_has_role('{LOGIN}','investalo_credentials_worker','MEMBER')
   OR EXISTS(SELECT FROM pg_catalog.pg_auth_members am JOIN pg_catalog.pg_roles r ON r.oid=am.roleid
     JOIN pg_catalog.pg_roles m ON m.oid=am.member
     WHERE m.rolname='{LOGIN}' AND (r.rolname<>'investalo_credentials_worker' OR am.admin_option))
 THEN RAISE EXCEPTION 'role privileges'; END IF;
END $$;
GRANT CONNECT ON DATABASE investalo TO {LOGIN};
COMMIT;
""")
    print("Exact Demo account and restricted credential LOGIN bound. Services unchanged.")


def backup():
    private(ROOT / "prepared")
    directory = ROOT / "backups"
    if not directory.exists():
        directory.mkdir(mode=0o700)
    metadata = directory.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ValueError()
    path = directory / (str(uuid4()) + ".pgdump")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(descriptor, "wb") as stream:
        result = subprocess.run(["bash", str(REPO / "infra/scripts/compose.sh"), "exec", "-T",
            "postgres", "pg_dump", "--username", "investalo_admin", "--dbname", "investalo",
            "--format=custom"], stdout=stream, stderr=subprocess.PIPE, timeout=120)
        stream.flush()
        os.fsync(stream.fileno())
    if result.returncode or path.stat().st_size < 32:
        raise ValueError()
    print("Private create-only database backup saved; no data printed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broker-uid")
    parser.add_argument("--parent-uid", default="0")
    parser.add_argument("--egress-ip", default="5.45.96.83")
    parser.add_argument("--created-in-demo-mode", action="store_true")
    parser.add_argument("--demo-without-ip-binding", action="store_true",
                        help="Explicit Demo-only setup when Bitget does not offer IP binding.")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--bind-account", action="store_true")
    actions.add_argument("--backup-database", action="store_true")
    args = parser.parse_args()
    try:
        if os.geteuid() != 0 or not (LOCAL / "READY").is_file():
            raise ValueError()
        if args.bind_account or args.backup_database:
            if args.broker_uid or args.created_in_demo_mode:
                raise ValueError()
            backup() if args.backup_database else bind()
        else:
            prepare(args)
        return 0
    except Exception:
        print("Demo setup refused or incomplete. Existing private files retained; no automatic retry.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
