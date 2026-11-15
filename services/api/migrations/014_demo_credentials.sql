-- Separate Classic Demo read secrets. Trusted private service primitives only;
-- no browser/passkey grant, account provisioning, key probe or trading enable.
ALTER TABLE platform.accounts DROP CONSTRAINT accounts_mode_check;
ALTER TABLE platform.accounts ADD CONSTRAINT accounts_mode_check
    CHECK(mode IN ('paper','mt5_demo','read_only','bitget_demo'));
ALTER TABLE platform.accounts ADD CONSTRAINT accounts_demo_profile
    CHECK(mode<>'bitget_demo' OR (broker='bitget' AND currency='USDT'));

CREATE TABLE platform.demo_credential_connections (
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    platform_account_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    broker_uid text NOT NULL UNIQUE CHECK(broker_uid ~ '^[1-9][0-9]{0,19}$'),
    parent_uid text NOT NULL CHECK(parent_uid='0' OR parent_uid ~ '^[1-9][0-9]{0,19}$'),
    environment text NOT NULL DEFAULT 'demo' CHECK(environment='demo'),
    api_family text NOT NULL DEFAULT 'classic' CHECK(api_family='classic'),
    position_mode text NOT NULL DEFAULT 'one_way_mode' CHECK(position_mode='one_way_mode'),
    leverage integer NOT NULL DEFAULT 2 CHECK(leverage=2),
    profile text NOT NULL DEFAULT 'bitget-classic-demo-read-secret/1'
        CHECK(profile='bitget-classic-demo-read-secret/1'),
    connection_mode text NOT NULL DEFAULT 'demo_read_only' CHECK(connection_mode='demo_read_only'),
    egress_ip text NOT NULL CHECK(length(egress_ip) BETWEEN 2 AND 45
        AND egress_ip ~ '^[0-9a-f:.]+$' AND egress_ip::inet IS NOT NULL),
    provisioning_digest text NOT NULL CHECK(provisioning_digest ~ '^[0-9a-f]{64}$'),
    credential_revision bigint NOT NULL CHECK(credential_revision=1),
    storage_version bigint NOT NULL CHECK(storage_version>0),
    status text NOT NULL CHECK(status IN ('active','revoked')),
    envelope jsonb NOT NULL CHECK(platform.credential_envelope_valid(envelope)),
    PRIMARY KEY(tenant_id,connection_id),
    UNIQUE(tenant_id,platform_account_id),
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id),
    FOREIGN KEY(tenant_id,platform_account_id) REFERENCES platform.accounts(tenant_id,id)
);
CREATE TABLE platform.demo_credential_audit (
    tenant_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    user_id uuid NOT NULL,
    storage_version bigint NOT NULL,
    credential_revision bigint NOT NULL CHECK(credential_revision=1),
    action text NOT NULL CHECK(action IN ('register','rewrap','revoke')),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(tenant_id,connection_id,storage_version),
    FOREIGN KEY(tenant_id,connection_id)
        REFERENCES platform.demo_credential_connections(tenant_id,connection_id)
);
ALTER TABLE platform.demo_credential_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.demo_credential_connections FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.demo_credential_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.demo_credential_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY migration_management ON platform.demo_credential_connections
    TO investalo_migration USING(true) WITH CHECK(true);
CREATE POLICY migration_management ON platform.demo_credential_audit
    TO investalo_migration USING(true) WITH CHECK(true);
REVOKE ALL ON platform.demo_credential_connections,platform.demo_credential_audit
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;

CREATE FUNCTION platform.demo_credential_context(p_epoch bigint,p_auth_ms bigint,p_expires_ms bigint)
RETURNS TABLE(tenant_id uuid,user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; user_row platform.users%ROWTYPE; now_ms bigint;
BEGIN
    SELECT * INTO STRICT actor FROM platform.credential_context();
    SELECT u.* INTO STRICT user_row FROM platform.users u WHERE u.id=actor.user_id FOR SHARE;
    now_ms:=floor(extract(epoch FROM clock_timestamp())*1000)::bigint;
    IF p_epoch IS NULL OR p_epoch<0 OR p_epoch>1000000000000000 OR p_epoch<>user_row.auth_epoch
       OR p_auth_ms IS NULL OR p_auth_ms<0 OR p_auth_ms>=1000000000000000
       OR p_auth_ms>now_ms+5000
       OR p_auth_ms<ceil(extract(epoch FROM user_row.reauth_after)*1000)
       OR p_expires_ms IS NULL OR p_expires_ms<=now_ms OR p_expires_ms>now_ms+60000 THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN QUERY SELECT actor.tenant_id,actor.user_id;
END $$;

CREATE FUNCTION platform.guard_demo_credential()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    ELSIF TG_OP='INSERT' THEN
        IF NEW.status<>'active' OR NEW.storage_version<>1 THEN
            RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
        END IF;
    ELSE
        IF OLD.status<>'active' OR OLD.storage_version=9223372036854775807
           OR NEW.storage_version<>OLD.storage_version+1
           OR (to_jsonb(NEW)-ARRAY['storage_version','status','envelope'])
              IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['storage_version','status','envelope'])
           OR (NEW.status='revoked' AND NEW.envelope IS DISTINCT FROM OLD.envelope)
           OR (NEW.status='active' AND
               (NEW.envelope->'payload_nonce' IS DISTINCT FROM OLD.envelope->'payload_nonce'
                OR NEW.envelope->'ciphertext' IS DISTINCT FROM OLD.envelope->'ciphertext')) THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER guarded_demo_credential BEFORE INSERT OR UPDATE OR DELETE
    ON platform.demo_credential_connections FOR EACH ROW EXECUTE FUNCTION platform.guard_demo_credential();
CREATE TRIGGER demo_credential_no_truncate BEFORE TRUNCATE
    ON platform.demo_credential_connections FOR EACH STATEMENT EXECUTE FUNCTION platform.guard_demo_credential();

CREATE FUNCTION platform.demo_credential_audit_write()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    INSERT INTO platform.demo_credential_audit
        (tenant_id,connection_id,user_id,storage_version,credential_revision,action)
        VALUES(NEW.tenant_id,NEW.connection_id,NEW.user_id,NEW.storage_version,NEW.credential_revision,
               CASE WHEN TG_OP='INSERT' THEN 'register'
                    WHEN NEW.status='revoked' THEN 'revoke' ELSE 'rewrap' END);
    RETURN NEW;
END $$;
CREATE TRIGGER demo_credential_audit_write AFTER INSERT OR UPDATE
    ON platform.demo_credential_connections FOR EACH ROW EXECUTE FUNCTION platform.demo_credential_audit_write();
CREATE FUNCTION platform.guard_demo_credential_audit()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
END $$;
CREATE TRIGGER immutable_demo_credential_audit BEFORE UPDATE OR DELETE
    ON platform.demo_credential_audit FOR EACH ROW EXECUTE FUNCTION platform.guard_demo_credential_audit();
CREATE TRIGGER demo_credential_audit_no_truncate BEFORE TRUNCATE
    ON platform.demo_credential_audit FOR EACH STATEMENT EXECUTE FUNCTION platform.guard_demo_credential_audit();

-- Helpers are private; SESSION_USER is independently provisioned and bound.
CREATE FUNCTION platform.demo_credential_owned(p_connection uuid,p_epoch bigint,
    p_auth_ms bigint,p_expires_ms bigint,p_revoke boolean DEFAULT false)
RETURNS platform.demo_credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; stored platform.demo_credential_connections%ROWTYPE;
BEGIN
    SELECT * INTO STRICT actor FROM platform.demo_credential_context(p_epoch,p_auth_ms,p_expires_ms);
    SELECT c.* INTO stored FROM platform.demo_credential_connections c
        JOIN platform.accounts a ON a.tenant_id=c.tenant_id AND a.id=c.platform_account_id
        WHERE c.tenant_id=actor.tenant_id AND c.user_id=actor.user_id AND c.connection_id=p_connection
          AND c.status='active' AND (p_revoke OR
              (a.broker='bitget' AND a.mode='bitget_demo' AND a.currency='USDT' AND a.status='ready'))
        FOR UPDATE OF c FOR SHARE OF a;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    RETURN stored;
END $$;

CREATE FUNCTION platform.demo_credential_create(p_account uuid,p_connection uuid,p_uid text,
    p_parent text,p_ip text,p_provenance text,p_envelope jsonb,
    p_epoch bigint,p_auth_ms bigint,p_expires_ms bigint)
RETURNS SETOF platform.demo_credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record;
BEGIN
    SELECT * INTO STRICT actor FROM platform.demo_credential_context(p_epoch,p_auth_ms,p_expires_ms);
    PERFORM 1 FROM platform.accounts a WHERE a.tenant_id=actor.tenant_id AND a.id=p_account
        AND a.broker='bitget' AND a.mode='bitget_demo' AND a.currency='USDT' AND a.status='ready'
        FOR SHARE OF a;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    IF p_connection IS NULL OR p_uid IS NULL OR NOT p_uid ~ '^[1-9][0-9]{0,19}$'
       OR p_parent IS NULL OR NOT (p_parent='0' OR p_parent ~ '^[1-9][0-9]{0,19}$')
       OR p_ip IS NULL OR length(p_ip) NOT BETWEEN 2 AND 45 OR NOT p_ip ~ '^[0-9a-f:.]+$'
       OR p_provenance IS NULL OR NOT p_provenance ~ '^[0-9a-f]{64}$'
       OR NOT platform.credential_envelope_valid(p_envelope) THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    RETURN QUERY INSERT INTO platform.demo_credential_connections
        (tenant_id,user_id,platform_account_id,connection_id,broker_uid,parent_uid,
         egress_ip,provisioning_digest,credential_revision,storage_version,status,envelope)
        VALUES(actor.tenant_id,actor.user_id,p_account,p_connection,p_uid,p_parent,p_ip,p_provenance,
               1,1,'active',p_envelope) RETURNING *;
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'identity_conflict' USING ERRCODE='23505';
WHEN invalid_text_representation OR check_violation THEN
    RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
END $$;

CREATE FUNCTION platform.demo_credential_read(p_connection uuid,p_epoch bigint,p_auth_ms bigint,p_expires_ms bigint)
RETURNS SETOF platform.demo_credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    RETURN NEXT platform.demo_credential_owned(p_connection,p_epoch,p_auth_ms,p_expires_ms);
END $$;
CREATE FUNCTION platform.demo_credential_rewrap(p_connection uuid,p_revision bigint,p_storage bigint,
    p_envelope jsonb,p_epoch bigint,p_auth_ms bigint,p_expires_ms bigint)
RETURNS SETOF platform.demo_credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE stored platform.demo_credential_connections%ROWTYPE;
BEGIN
    stored:=platform.demo_credential_owned(p_connection,p_epoch,p_auth_ms,p_expires_ms);
    IF p_revision IS DISTINCT FROM stored.credential_revision OR p_storage IS DISTINCT FROM stored.storage_version THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF stored.storage_version=9223372036854775807 OR NOT platform.credential_envelope_valid(p_envelope)
       OR p_envelope->'payload_nonce' IS DISTINCT FROM stored.envelope->'payload_nonce'
       OR p_envelope->'ciphertext' IS DISTINCT FROM stored.envelope->'ciphertext' THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    RETURN QUERY UPDATE platform.demo_credential_connections c SET envelope=p_envelope,storage_version=c.storage_version+1
        WHERE c.tenant_id=stored.tenant_id AND c.connection_id=stored.connection_id RETURNING c.*;
END $$;
CREATE FUNCTION platform.demo_credential_revoke(p_connection uuid,p_revision bigint,p_storage bigint,
    p_epoch bigint,p_auth_ms bigint,p_expires_ms bigint)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE stored platform.demo_credential_connections%ROWTYPE; version bigint;
BEGIN
    stored:=platform.demo_credential_owned(p_connection,p_epoch,p_auth_ms,p_expires_ms,true);
    IF p_revision IS DISTINCT FROM stored.credential_revision OR p_storage IS DISTINCT FROM stored.storage_version THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF stored.storage_version=9223372036854775807 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    UPDATE platform.demo_credential_connections c SET status='revoked',storage_version=c.storage_version+1
        WHERE c.tenant_id=stored.tenant_id AND c.connection_id=stored.connection_id RETURNING c.storage_version INTO version;
    RETURN version;
END $$;

REVOKE ALL ON FUNCTION platform.demo_credential_context(bigint,bigint,bigint),
    platform.guard_demo_credential(),platform.demo_credential_audit_write(),platform.guard_demo_credential_audit(),
    platform.demo_credential_owned(uuid,bigint,bigint,bigint,boolean),
    platform.demo_credential_create(uuid,uuid,text,text,text,text,jsonb,bigint,bigint,bigint),
    platform.demo_credential_read(uuid,bigint,bigint,bigint),
    platform.demo_credential_rewrap(uuid,bigint,bigint,jsonb,bigint,bigint,bigint),
    platform.demo_credential_revoke(uuid,bigint,bigint,bigint,bigint,bigint)
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION platform.demo_credential_context(bigint,bigint,bigint),
    platform.demo_credential_create(uuid,uuid,text,text,text,text,jsonb,bigint,bigint,bigint),
    platform.demo_credential_read(uuid,bigint,bigint,bigint),
    platform.demo_credential_rewrap(uuid,bigint,bigint,jsonb,bigint,bigint,bigint),
    platform.demo_credential_revoke(uuid,bigint,bigint,bigint,bigint,bigint)
    TO investalo_credentials_worker;
