-- Separate Demo trading purpose, shared immutable Demo UID/account registry.
-- No key intake, passkey issuance, HTTP enablement or order authority.
CREATE FUNCTION platform.demo_trading_authorities_valid(p_value jsonb)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE items text[];
BEGIN
    IF p_value IS NULL OR jsonb_typeof(p_value)<>'array' THEN RETURN false; END IF;
    IF jsonb_array_length(p_value) NOT BETWEEN 3 AND 12 OR EXISTS(
        SELECT 1 FROM jsonb_array_elements(p_value) e WHERE jsonb_typeof(e)<>'string'
    ) THEN RETURN false; END IF;
    SELECT array_agg(e.value#>>'{}' ORDER BY e.ordinality) INTO items
        FROM jsonb_array_elements(p_value) WITH ORDINALITY e(value,ordinality);
    RETURN items @> ARRAY['coow','cpow','stow']::text[]
       AND items <@ ARRAY['coow','cpow','stow','stor','coor','cpor','smor','ttor',
                         'wtor','taxr','chor','p2pr']::text[]
       AND cardinality(items)=(SELECT count(DISTINCT item) FROM unnest(items) item)
       AND items=(SELECT array_agg(item ORDER BY item COLLATE "C") FROM unnest(items) item);
END $$;

ALTER TABLE platform.demo_credential_connections ADD COLUMN authorities jsonb;
ALTER TABLE platform.demo_credential_connections
    DROP CONSTRAINT demo_credential_connections_profile_check,
    DROP CONSTRAINT demo_credential_connections_connection_mode_check;
ALTER TABLE platform.demo_credential_connections ADD CONSTRAINT demo_credential_profile_binding
    CHECK((profile='bitget-classic-demo-read-secret/1' AND connection_mode='demo_read_only'
            AND authorities IS NULL)
       OR (profile='bitget-classic-demo-trading-secret/1' AND connection_mode='demo_futures_spot_trading'
            AND authorities IS NOT NULL AND platform.demo_trading_authorities_valid(authorities)));
-- Existing guard compares all immutable columns, including authorities.
-- Existing unique UID/account constraints and audit survive revocation.

CREATE FUNCTION platform.demo_credential_owned_profile(p_connection uuid,p_epoch bigint,
    p_auth_ms bigint,p_expires_ms bigint,p_revoke boolean,p_profile text)
RETURNS platform.demo_credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; stored platform.demo_credential_connections%ROWTYPE; purpose text;
BEGIN
    IF p_profile='bitget-classic-demo-read-secret/1' THEN purpose:='demo_read_only';
    ELSIF p_profile='bitget-classic-demo-trading-secret/1' THEN purpose:='demo_futures_spot_trading';
    ELSE RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    SELECT * INTO STRICT actor FROM platform.demo_credential_context(p_epoch,p_auth_ms,p_expires_ms);
    SELECT c.* INTO stored FROM platform.demo_credential_connections c
        JOIN platform.accounts a ON a.tenant_id=c.tenant_id AND a.id=c.platform_account_id
        WHERE c.tenant_id=actor.tenant_id AND c.user_id=actor.user_id AND c.connection_id=p_connection
          AND c.profile=p_profile AND c.connection_mode=purpose AND c.status='active'
          AND (p_revoke OR (a.broker='bitget' AND a.mode='bitget_demo'
               AND a.currency='USDT' AND a.status='ready'))
        FOR UPDATE OF c FOR SHARE OF a;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    RETURN stored;
END $$;

CREATE OR REPLACE FUNCTION platform.demo_credential_owned(p_connection uuid,p_epoch bigint,
    p_auth_ms bigint,p_expires_ms bigint,p_revoke boolean DEFAULT false)
RETURNS platform.demo_credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    RETURN platform.demo_credential_owned_profile(p_connection,p_epoch,p_auth_ms,p_expires_ms,
        p_revoke,'bitget-classic-demo-read-secret/1');
END $$;

CREATE FUNCTION platform.demo_trading_credential_create(p_account uuid,p_connection uuid,p_uid text,
    p_parent text,p_ip text,p_provenance text,p_authorities jsonb,p_envelope jsonb,
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
       OR NOT platform.demo_trading_authorities_valid(p_authorities)
       OR NOT platform.credential_envelope_valid(p_envelope) THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    RETURN QUERY INSERT INTO platform.demo_credential_connections
        (tenant_id,user_id,platform_account_id,connection_id,broker_uid,parent_uid,
         profile,connection_mode,authorities,egress_ip,provisioning_digest,
         credential_revision,storage_version,status,envelope)
        VALUES(actor.tenant_id,actor.user_id,p_account,p_connection,p_uid,p_parent,
            'bitget-classic-demo-trading-secret/1','demo_futures_spot_trading',p_authorities,
            p_ip,p_provenance,1,1,'active',p_envelope) RETURNING *;
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'identity_conflict' USING ERRCODE='23505';
WHEN invalid_text_representation OR check_violation THEN
    RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
END $$;

CREATE FUNCTION platform.demo_trading_credential_read(p_connection uuid,p_epoch bigint,
    p_auth_ms bigint,p_expires_ms bigint)
RETURNS SETOF platform.demo_credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    RETURN NEXT platform.demo_credential_owned_profile(p_connection,p_epoch,p_auth_ms,p_expires_ms,
        false,'bitget-classic-demo-trading-secret/1');
END $$;

CREATE FUNCTION platform.demo_trading_credential_rewrap(p_connection uuid,p_revision bigint,p_storage bigint,
    p_envelope jsonb,p_epoch bigint,p_auth_ms bigint,p_expires_ms bigint)
RETURNS SETOF platform.demo_credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE stored platform.demo_credential_connections%ROWTYPE;
BEGIN
    stored:=platform.demo_credential_owned_profile(p_connection,p_epoch,p_auth_ms,p_expires_ms,
        false,'bitget-classic-demo-trading-secret/1');
    IF p_revision IS DISTINCT FROM stored.credential_revision OR p_storage IS DISTINCT FROM stored.storage_version THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF stored.storage_version=9223372036854775807 OR NOT platform.credential_envelope_valid(p_envelope)
       OR p_envelope->'payload_nonce' IS DISTINCT FROM stored.envelope->'payload_nonce'
       OR p_envelope->'ciphertext' IS DISTINCT FROM stored.envelope->'ciphertext' THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    RETURN QUERY UPDATE platform.demo_credential_connections c
        SET envelope=p_envelope,storage_version=c.storage_version+1
        WHERE c.tenant_id=stored.tenant_id AND c.connection_id=stored.connection_id RETURNING c.*;
END $$;

CREATE FUNCTION platform.demo_trading_credential_revoke(p_connection uuid,p_revision bigint,p_storage bigint,
    p_epoch bigint,p_auth_ms bigint,p_expires_ms bigint)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE stored platform.demo_credential_connections%ROWTYPE; version bigint;
BEGIN
    stored:=platform.demo_credential_owned_profile(p_connection,p_epoch,p_auth_ms,p_expires_ms,
        true,'bitget-classic-demo-trading-secret/1');
    IF p_revision IS DISTINCT FROM stored.credential_revision OR p_storage IS DISTINCT FROM stored.storage_version THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF stored.storage_version=9223372036854775807 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    UPDATE platform.demo_credential_connections c SET status='revoked',storage_version=c.storage_version+1
        WHERE c.tenant_id=stored.tenant_id AND c.connection_id=stored.connection_id
        RETURNING c.storage_version INTO version;
    RETURN version;
END $$;

-- Internal explicit projection; only independently scoped wrappers may call it.
CREATE FUNCTION platform.demo_credential_profile_metadata(p_tenant uuid,p_user uuid,p_epoch bigint,
    p_account uuid,p_action text,p_profile text)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE a record; c record; purpose text; result jsonb;
BEGIN
    IF p_profile='bitget-classic-demo-read-secret/1' THEN purpose:='demo_read_only';
    ELSIF p_profile='bitget-classic-demo-trading-secret/1' THEN purpose:='demo_futures_spot_trading';
    ELSE RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    IF p_action IS NULL OR p_action NOT IN ('register','revoke','view') THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    IF p_action='register' THEN
        SELECT x.id,x.name,x.broker,x.mode,x.currency,x.status INTO a FROM platform.accounts x
            WHERE x.tenant_id=p_tenant AND x.id=p_account FOR UPDATE OF x;
    ELSE
        SELECT x.id,x.name,x.broker,x.mode,x.currency,x.status INTO a FROM platform.accounts x
            WHERE x.tenant_id=p_tenant AND x.id=p_account FOR SHARE OF x;
    END IF;
    IF NOT FOUND OR a.broker<>'bitget' OR a.mode<>'bitget_demo' OR a.currency<>'USDT'
       OR (p_action='register' AND a.status<>'ready') THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF p_action='view' THEN
        SELECT x.user_id,x.connection_id,x.credential_revision,x.storage_version,x.status,
               x.profile,x.connection_mode,x.authorities INTO c
            FROM platform.demo_credential_connections x
            WHERE x.tenant_id=p_tenant AND x.platform_account_id=p_account FOR SHARE OF x;
    ELSE
        SELECT x.user_id,x.connection_id,x.credential_revision,x.storage_version,x.status,
               x.profile,x.connection_mode,x.authorities INTO c
            FROM platform.demo_credential_connections x
            WHERE x.tenant_id=p_tenant AND x.platform_account_id=p_account FOR UPDATE OF x;
    END IF;
    IF FOUND AND (c.user_id<>p_user OR c.profile<>p_profile OR c.connection_mode<>purpose) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    result:=jsonb_build_object('tenant_id',p_tenant,'auth_epoch',p_epoch,
        'purpose',purpose,'profile',p_profile,'environment','demo',
        'account',jsonb_build_object('id',a.id,'name',a.name,'broker',a.broker,'mode',a.mode,
                                    'currency',a.currency,'status',a.status),
        'connection',CASE WHEN c.connection_id IS NULL THEN NULL ELSE
            jsonb_build_object('connection_id',c.connection_id,'credential_revision',c.credential_revision,
                'storage_version',c.storage_version,'status',c.status) END);
    IF purpose='demo_futures_spot_trading' THEN
        result:=result||jsonb_build_object('key_authorities',c.authorities);
    END IF;
    RETURN result;
END $$;

CREATE OR REPLACE FUNCTION platform.demo_credential_passkey_metadata(p_tenant uuid,p_user uuid,p_epoch bigint,
    p_account uuid,p_action text)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF p_action IS NULL OR p_action NOT IN ('register','revoke') THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    RETURN platform.demo_credential_profile_metadata(p_tenant,p_user,p_epoch,p_account,p_action,
        'bitget-classic-demo-read-secret/1');
END $$;

CREATE FUNCTION platform.demo_trading_credential_passkey_metadata(p_tenant uuid,p_user uuid,p_epoch bigint,
    p_account uuid,p_action text)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF p_action IS NULL OR p_action NOT IN ('register','revoke') THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    RETURN platform.demo_credential_profile_metadata(p_tenant,p_user,p_epoch,p_account,p_action,
        'bitget-classic-demo-trading-secret/1');
END $$;

CREATE OR REPLACE FUNCTION platform.demo_credential_action_context(
    p_account uuid,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    RETURN platform.demo_credential_profile_metadata(actor.tenant_id,actor.user_id,actor.auth_epoch,
        p_account,'view','bitget-classic-demo-read-secret/1');
END $$;

CREATE FUNCTION platform.demo_trading_credential_action_context(
    p_account uuid,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    RETURN platform.demo_credential_profile_metadata(actor.tenant_id,actor.user_id,actor.auth_epoch,
        p_account,'view','bitget-classic-demo-trading-secret/1');
END $$;

REVOKE ALL ON FUNCTION platform.demo_trading_authorities_valid(jsonb),
    platform.demo_credential_owned_profile(uuid,bigint,bigint,bigint,boolean,text),
    platform.demo_trading_credential_create(uuid,uuid,text,text,text,text,jsonb,jsonb,bigint,bigint,bigint),
    platform.demo_trading_credential_read(uuid,bigint,bigint,bigint),
    platform.demo_trading_credential_rewrap(uuid,bigint,bigint,jsonb,bigint,bigint,bigint),
    platform.demo_trading_credential_revoke(uuid,bigint,bigint,bigint,bigint,bigint),
    platform.demo_credential_profile_metadata(uuid,uuid,bigint,uuid,text,text),
    platform.demo_trading_credential_passkey_metadata(uuid,uuid,bigint,uuid,text),
    platform.demo_trading_credential_action_context(uuid,bigint,bigint)
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION
    platform.demo_trading_credential_create(uuid,uuid,text,text,text,text,jsonb,jsonb,bigint,bigint,bigint),
    platform.demo_trading_credential_read(uuid,bigint,bigint,bigint),
    platform.demo_trading_credential_rewrap(uuid,bigint,bigint,jsonb,bigint,bigint,bigint),
    platform.demo_trading_credential_revoke(uuid,bigint,bigint,bigint,bigint,bigint)
    TO investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION platform.demo_trading_credential_action_context(uuid,bigint,bigint)
    TO investalo_runtime;
