-- Paper planning only; no balance, order, credential or worker authority.
CREATE TABLE platform.futures_paper_settings (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision > 0),
    basket_limit smallint NOT NULL CHECK(basket_limit BETWEEN 3 AND 7),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,account_id),
    FOREIGN KEY(tenant_id,account_id) REFERENCES platform.accounts(tenant_id,id)
);
CREATE TABLE platform.futures_paper_settings_audit (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision > 0),
    actor_id uuid NOT NULL,
    basket_limit smallint NOT NULL CHECK(basket_limit BETWEEN 3 AND 7),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,account_id,revision),
    FOREIGN KEY(tenant_id,account_id) REFERENCES platform.accounts(tenant_id,id),
    FOREIGN KEY(tenant_id,actor_id) REFERENCES platform.memberships(tenant_id,user_id)
);
ALTER TABLE platform.futures_paper_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.futures_paper_settings FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.futures_paper_settings_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.futures_paper_settings_audit FORCE ROW LEVEL SECURITY;

CREATE POLICY own_paper_settings_read ON platform.futures_paper_settings
FOR SELECT TO investalo_runtime USING(
    tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
    AND EXISTS(SELECT 1 FROM platform.accounts a WHERE a.tenant_id=futures_paper_settings.tenant_id
      AND a.id=account_id AND a.broker='bitget' AND a.mode='paper' AND a.currency='USDT')
);
CREATE POLICY own_paper_settings_write ON platform.futures_paper_settings
FOR ALL TO investalo_runtime USING(
    tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
    AND EXISTS(SELECT 1 FROM platform.memberships m WHERE m.tenant_id=futures_paper_settings.tenant_id
      AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
      AND m.active AND m.role IN ('owner','trader'))
    AND EXISTS(SELECT 1 FROM platform.accounts a WHERE a.tenant_id=futures_paper_settings.tenant_id
      AND a.id=account_id AND a.broker='bitget' AND a.mode='paper' AND a.currency='USDT')
) WITH CHECK(
    tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
    AND EXISTS(SELECT 1 FROM platform.memberships m WHERE m.tenant_id=futures_paper_settings.tenant_id
      AND m.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
      AND m.active AND m.role IN ('owner','trader'))
    AND EXISTS(SELECT 1 FROM platform.accounts a WHERE a.tenant_id=futures_paper_settings.tenant_id
      AND a.id=account_id AND a.broker='bitget' AND a.mode='paper' AND a.currency='USDT')
);
CREATE POLICY own_paper_settings_audit ON platform.futures_paper_settings_audit
FOR INSERT TO investalo_runtime WITH CHECK(
    tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
    AND actor_id=NULLIF(current_setting('app.user_id',true),'')::uuid
    AND EXISTS(SELECT 1 FROM platform.memberships m WHERE m.tenant_id=futures_paper_settings_audit.tenant_id
      AND m.user_id=actor_id AND m.active AND m.role IN ('owner','trader'))
    AND EXISTS(SELECT 1 FROM platform.accounts a WHERE a.tenant_id=futures_paper_settings_audit.tenant_id
      AND a.id=account_id AND a.broker='bitget' AND a.mode='paper' AND a.currency='USDT')
);
CREATE POLICY migration_management ON platform.futures_paper_settings
TO investalo_migration USING(true) WITH CHECK(true);
CREATE POLICY migration_management ON platform.futures_paper_settings_audit
TO investalo_migration USING(true) WITH CHECK(true);
REVOKE ALL ON platform.futures_paper_settings,platform.futures_paper_settings_audit
FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_paper_worker,investalo_credentials_worker;
GRANT SELECT,INSERT,UPDATE ON platform.futures_paper_settings TO investalo_runtime;
GRANT INSERT ON platform.futures_paper_settings_audit TO investalo_runtime;
