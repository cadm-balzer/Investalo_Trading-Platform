#!/usr/bin/env python3
"""Fully rolled-back014 preflight; optional fixture-only reviewed application."""
import argparse
import base64
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
    for number in range(1, 14):
        path, = directory.glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError()
    development = sql("SELECT json_agg(json_build_array(version,checksum) ORDER BY version) "
                      "FROM platform.schema_migrations;", database="investalo")
    print("PASS: fixture001–013 immutable checksums verified", flush=True)
    path = directory/"014_demo_credentials.sql"
    content, checksum = path.read_text(), hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stem in recorded:
        if recorded[path.stem] != checksum:
            raise ValueError()
        print("PASS: immutable fixture014 matches", flush=True)
    else:
        tenant, user, account, connection = [uuid4() for _ in range(4)]
        # Shape-only synthetic ciphertext; SQL cannot prove AES-GCM/key provenance.
        envelope = json.dumps(dict(schema_version="credential-envelope/1", kek_id="synthetic-preflight",
            payload_nonce=base64.b64encode(bytes(12)).decode(),
            wrap_nonce=base64.b64encode(bytes(12)).decode(),
            wrapped_dek=base64.b64encode(bytes(48)).decode(),
            ciphertext=base64.b64encode(bytes(17)).decode()))
        sql(f"""
BEGIN; SET LOCAL ROLE investalo_migration;
{content}
INSERT INTO platform.tenants(id,name) VALUES('{tenant}','Synthetic Demo preflight');
INSERT INTO platform.users(id,oidc_issuer,oidc_subject)
VALUES('{user}','https://demo-preflight.invalid','{user}');
INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES('{tenant}','{user}','owner');
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)
VALUES('{tenant}','{account}','Synthetic Demo','bitget','bitget_demo','USDT','ready');
UPDATE platform.credential_role_bindings SET tenant_id='{tenant}',user_id='{user}'
WHERE database_role='investalo_credentials_tests_a';
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_credentials_tests_a;
DO $$
DECLARE now_ms bigint:=floor(extract(epoch FROM clock_timestamp())*1000)::bigint; result record;
BEGIN
 SELECT * INTO STRICT result FROM platform.demo_credential_create(
   '{account}','{connection}','991122334455','0','192.0.2.8','{'d'*64}',
   '{envelope}'::jsonb,0,now_ms,now_ms+30000);
 IF result.storage_version<>1 OR result.connection_mode<>'demo_read_only' THEN
   RAISE EXCEPTION 'create'; END IF;
 SELECT * INTO STRICT result FROM platform.demo_credential_read('{connection}',0,now_ms,now_ms+30000);
 BEGIN
   PERFORM platform.credential_read('{connection}'); RAISE EXCEPTION 'normal profile accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
   PERFORM platform.demo_credential_read('{connection}',1,now_ms,now_ms+30000);
   RAISE EXCEPTION 'foreign epoch accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
   PERFORM platform.demo_credential_read('{connection}',0,now_ms,now_ms);
   RAISE EXCEPTION 'expired accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
   PERFORM 1 FROM platform.demo_credential_connections; RAISE EXCEPTION 'table grant';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 IF platform.demo_credential_revoke('{connection}',1,1,0,now_ms,now_ms+30000)<>2 THEN
   RAISE EXCEPTION 'revoke'; END IF;
 BEGIN
   PERFORM platform.demo_credential_read('{connection}',0,now_ms,now_ms+30000);
   RAISE EXCEPTION 'revoked accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET SESSION AUTHORIZATION; SET LOCAL ROLE investalo_migration;
DO $$ BEGIN
 IF (SELECT count(*) FROM platform.demo_credential_audit WHERE connection_id='{connection}')<>2 THEN
   RAISE EXCEPTION 'audit'; END IF;
 BEGIN
   DELETE FROM platform.demo_credential_audit WHERE connection_id='{connection}';
   RAISE EXCEPTION 'audit deletion';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
ROLLBACK;
""")
        print("PASS:014 DDL/create/read/epoch/expiry/profile/revoke/audit preflight fully rolled back", flush=True)
        if args.apply_reviewed:
            sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
                +content+f"\nINSERT INTO platform.schema_migrations(version,checksum)"
                f" VALUES('{path.stem}','{checksum}'); COMMIT;")
            print("PASS: reviewed014 applied ONLY to investalo_credentials_checks", flush=True)
    if development != sql("SELECT json_agg(json_build_array(version,checksum) ORDER BY version) "
                          "FROM platform.schema_migrations;", database="investalo"):
        raise ValueError()
    print("PASS: development migration set unchanged")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Demo credential fixture preparation rejected; sensitive output suppressed") from None
