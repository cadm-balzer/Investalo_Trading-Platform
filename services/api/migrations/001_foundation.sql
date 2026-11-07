-- Run as investalo_migration. Authentication provisioning is administrative.
REVOKE ALL ON SCHEMA platform FROM PUBLIC;
GRANT USAGE ON SCHEMA platform TO investalo_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA platform REVOKE ALL ON TABLES FROM PUBLIC;

CREATE TABLE platform.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    oidc_issuer text NOT NULL,
    oidc_subject text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    auth_epoch bigint NOT NULL DEFAULT 0 CHECK(auth_epoch >= 0),
    reauth_after timestamptz NOT NULL DEFAULT '1970-01-01T00:00:00Z',
    UNIQUE(oidc_issuer, oidc_subject)
);
CREATE TABLE platform.tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL CHECK(length(name) BETWEEN 1 AND 120)
);
CREATE TABLE platform.memberships (
    tenant_id uuid NOT NULL REFERENCES platform.tenants(id),
    user_id uuid NOT NULL REFERENCES platform.users(id),
    role text NOT NULL CHECK(role IN ('owner','trader','researcher','viewer')),
    active boolean NOT NULL DEFAULT true,
    PRIMARY KEY(tenant_id,user_id)
);
CREATE TABLE platform.request_nonces (
    jti uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES platform.users(id),
    expires_at timestamptz NOT NULL
);
CREATE INDEX ON platform.request_nonces(expires_at);
CREATE TABLE platform.instruments (
    symbol text PRIMARY KEY,
    venue text NOT NULL,
    base_asset text NOT NULL,
    quote_asset text NOT NULL
);
INSERT INTO platform.instruments VALUES
    ('BTC/USDT','bitget','BTC','USDT'), ('ETH/USDT','bitget','ETH','USDT');
CREATE TABLE platform.accounts (
    tenant_id uuid NOT NULL REFERENCES platform.tenants(id),
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    name text NOT NULL,
    broker text NOT NULL CHECK(broker IN ('bitget','mt5')),
    mode text NOT NULL CHECK(mode IN ('paper','mt5_demo','read_only')),
    currency text NOT NULL,
    status text NOT NULL DEFAULT 'disconnected' CHECK(status IN ('disconnected','ready','paused')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,id)
);
CREATE TABLE platform.positions (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    symbol text NOT NULL,
    quantity numeric(38,18) NOT NULL CHECK(quantity >= 0),
    average_price numeric(38,18) NOT NULL CHECK(average_price >= 0),
    observed_at timestamptz NOT NULL,
    PRIMARY KEY(tenant_id,account_id,symbol),
    FOREIGN KEY(tenant_id,account_id) REFERENCES platform.accounts(tenant_id,id)
);
CREATE TABLE platform.journal (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    account_id uuid NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,id),
    FOREIGN KEY(tenant_id,account_id) REFERENCES platform.accounts(tenant_id,id)
);
CREATE TABLE platform.jobs (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    created_by uuid NOT NULL,
    kind text NOT NULL CHECK(kind IN ('backtest')),
    status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK(length(payload_hash)=64),
    idempotency_key uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    lease_until timestamptz,
    result jsonb,
    PRIMARY KEY(tenant_id,id),
    UNIQUE(tenant_id,idempotency_key),
    FOREIGN KEY(tenant_id,created_by) REFERENCES platform.memberships(tenant_id,user_id)
);
CREATE INDEX ON platform.jobs(status,created_at);
CREATE TABLE platform.order_intents (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    account_id uuid NOT NULL,
    strategy_version text NOT NULL,
    risk_version text NOT NULL,
    mode text NOT NULL CHECK(mode IN ('paper','mt5_demo')),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,id),
    FOREIGN KEY(tenant_id,account_id) REFERENCES platform.accounts(tenant_id,id)
);
CREATE TABLE platform.outbox (
    tenant_id uuid NOT NULL,
    id uuid NOT NULL,
    intent_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    lease_until timestamptz,
    PRIMARY KEY(tenant_id,id),
    UNIQUE(tenant_id,intent_id),
    FOREIGN KEY(tenant_id,intent_id) REFERENCES platform.order_intents(tenant_id,id)
);

ALTER TABLE platform.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.users FORCE ROW LEVEL SECURITY;
CREATE POLICY own_identity ON platform.users TO investalo_runtime
    USING(oidc_issuer=current_setting('app.oidc_issuer',true)
      AND oidc_subject=current_setting('app.oidc_subject',true));
ALTER TABLE platform.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY own_membership ON platform.memberships TO investalo_runtime
    USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
ALTER TABLE platform.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY member_tenant ON platform.tenants TO investalo_runtime
    USING(EXISTS(SELECT 1 FROM platform.memberships m
      WHERE m.tenant_id=id AND m.active));
ALTER TABLE platform.request_nonces ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.request_nonces FORCE ROW LEVEL SECURITY;
CREATE POLICY own_nonce ON platform.request_nonces TO investalo_runtime
    USING(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid)
    WITH CHECK(user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);

DO $$
DECLARE item text;
BEGIN
  FOREACH item IN ARRAY ARRAY['accounts','positions','journal','jobs','order_intents','outbox']
  LOOP
    EXECUTE format('ALTER TABLE platform.%I ENABLE ROW LEVEL SECURITY',item);
    EXECUTE format('ALTER TABLE platform.%I FORCE ROW LEVEL SECURITY',item);
    EXECUTE format('CREATE POLICY tenant_boundary ON platform.%I TO investalo_runtime
      USING(tenant_id=NULLIF(current_setting(''app.tenant_id'',true),'''')::uuid)
      WITH CHECK(tenant_id=NULLIF(current_setting(''app.tenant_id'',true),'''')::uuid)',item);
  END LOOP;
END $$;

-- Migration owner needs explicit policies because FORCE RLS also covers owners.
DO $$
DECLARE item text;
BEGIN
  FOREACH item IN ARRAY ARRAY[
    'users','memberships','tenants','request_nonces','accounts','positions','journal',
    'jobs','order_intents','outbox']
  LOOP
    EXECUTE format('CREATE POLICY migration_management ON platform.%I
      TO investalo_migration USING(true) WITH CHECK(true)',item);
  END LOOP;
END $$;
GRANT SELECT ON ALL TABLES IN SCHEMA platform TO investalo_runtime;
GRANT INSERT ON platform.request_nonces, platform.jobs TO investalo_runtime;
-- No runtime UPDATE/DELETE/TRUNCATE, DDL, table ownership or live mode.
