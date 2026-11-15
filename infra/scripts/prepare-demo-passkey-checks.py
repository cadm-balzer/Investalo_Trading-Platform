#!/usr/bin/env python3
"""Fully rolled-back015 preflight; optional fixture-only reviewed application."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-reviewed", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError()
    root = Path(__file__).resolve().parents[2]
    sql = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))["sql"]
    directory = root/"services/api/migrations"
    recorded = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;")))
    for number in range(1, 15):
        path, = directory.glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError()
    development = sql("SELECT json_agg(json_build_array(version,checksum) ORDER BY version) "
                      "FROM platform.schema_migrations;", database="investalo")
    print("PASS: fixture001–014 immutable checksums verified", flush=True)
    path = directory/"015_demo_passkey_authorizations.sql"
    content, checksum = path.read_text(), hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stem in recorded:
        if recorded[path.stem] != checksum:
            raise ValueError()
        print("PASS: immutable fixture015 matches", flush=True)
    else:
        tenant, user, account, connection = [uuid4() for _ in range(4)]
        factor = uuid4()
        sql(f"""
BEGIN; SET LOCAL ROLE investalo_migration;
{content}
INSERT INTO platform.tenants(id,name) VALUES('{tenant}','Synthetic Demo purpose');
INSERT INTO platform.users(id,oidc_issuer,oidc_subject)
VALUES('{user}','https://demo-purpose.invalid','{user}');
INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES('{tenant}','{user}','owner');
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)
VALUES('{tenant}','{account}','Synthetic Demo','bitget','bitget_demo','USDT','ready');
INSERT INTO platform.passkey_credentials
(passkey_id,tenant_id,user_id,rp_id,credential_id,user_handle,public_key,oidc_issuer,oidc_subject,
 enrollment_epoch,sign_count,backup_eligible,backed_up)
VALUES('{factor}','{tenant}','{user}','cockpit.local.test',decode('{uuid4().hex}','hex'),
 decode(repeat('ab',32),'hex'),decode(repeat('cd',32),'hex'),
 'https://demo-purpose.invalid','{user}',0,0,true,false);
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_runtime;
SELECT set_config('app.user_id','{user}',true),set_config('app.tenant_id','{tenant}',true),
set_config('app.oidc_issuer','https://demo-purpose.invalid',true),set_config('app.oidc_subject','{user}',true);
DO $$
DECLARE n bigint:=floor(extract(epoch FROM clock_timestamp()))::bigint; p record;
BEGIN
 SELECT * INTO STRICT p FROM platform.demo_passkey_credential_prepare(
 '{account}','register','{connection}','cockpit.local.test','https://cockpit.local.test:8443',
 decode(repeat('aa',32),'hex'),decode(repeat('bb',32),'hex'),decode(repeat('cc',32),'hex'),
 repeat('d',64),n+600,0,n-600);
 IF p.metadata->>'purpose'<>'demo_read_only' OR p.metadata->'account'->>'mode'<>'bitget_demo' THEN
   RAISE EXCEPTION 'scope'; END IF;
 BEGIN
  PERFORM platform.passkey_action_claim(p.attempt_id,'cockpit.local.test',p.session_binding,0,n-600);
  RAISE EXCEPTION 'legacy claim';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 PERFORM platform.demo_passkey_action_claim(p.attempt_id,'cockpit.local.test',p.session_binding,0,n-600);
 BEGIN
  PERFORM 1 FROM platform.demo_passkey_credential_authorizations; RAISE EXCEPTION 'direct table';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
ROLLBACK;
""")
        print("PASS:015 DDL/own preparation/shared factor/Demo-vs-normal claim preflight fully rolled back", flush=True)
        if args.apply_reviewed:
            sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
                +content+f"\nINSERT INTO platform.schema_migrations(version,checksum)"
                f" VALUES('{path.stem}','{checksum}'); COMMIT;")
            print("PASS: reviewed015 applied ONLY to investalo_credentials_checks", flush=True)
    if development != sql("SELECT json_agg(json_build_array(version,checksum) ORDER BY version) "
                          "FROM platform.schema_migrations;", database="investalo"):
        raise ValueError()
    print("PASS: development migration set unchanged")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Demo passkey fixture preparation rejected; sensitive output suppressed") from None
