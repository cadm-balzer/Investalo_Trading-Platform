#!/usr/bin/env python3
"""Create one synthetic fixture account/binding for a bounded public-feed run."""
import hashlib
import os
from pathlib import Path
import runpy
from uuid import uuid4


def main():
    root = Path(__file__).resolve().parents[2]
    if os.geteuid() != 0:
        raise ValueError()
    prep = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))
    sql = prep["sql"]
    migration = root/"services/api/migrations/010_paper_state.sql"
    expected = hashlib.sha256(migration.read_bytes()).hexdigest()
    if sql("SELECT checksum FROM platform.schema_migrations WHERE version='010_paper_state';") != expected:
        raise ValueError()
    tenant, account = uuid4(), uuid4()
    sql(f"""
BEGIN;
INSERT INTO platform.tenants(id,name) VALUES('{tenant}','Public feed Paper fixture');
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)
VALUES('{tenant}','{account}','Public feed simulated Paper','bitget','paper','USDT','ready');
INSERT INTO platform.paper_role_bindings(database_role,tenant_id,account_id)
VALUES('investalo_paper_tests','{tenant}','{account}')
ON CONFLICT(database_role) DO UPDATE SET tenant_id=excluded.tenant_id,
account_id=excluded.account_id,active=true;
COMMIT;
""")
    path = root/f"infra/local/paper-feed-{account}.env"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(f"PAPER_TENANT_ID={tenant}\nPAPER_ACCOUNT_ID={account}\n")
    print(f"Prepared synthetic fixture only; environment file: {path}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper public-feed fixture preparation rejected") from None
