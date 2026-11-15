-- Own metadata-only runtime boundary. No keys, private reads or write authority.
-- Existing001–016 and their purpose/consume/completion contracts stay unchanged.
CREATE FUNCTION platform.demo_credential_action_context(
    p_account uuid,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; account_row record; connection_row record;
BEGIN
    -- Rechecks the actual restricted runtime LOGIN, original OIDC actor,
    -- active owner/trader membership, current epoch and reauth_after under lock.
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    IF p_account IS NULL THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    SELECT a.id,a.name,a.broker,a.mode,a.currency,a.status INTO account_row
        FROM platform.accounts a WHERE a.tenant_id=actor.tenant_id AND a.id=p_account
          AND a.broker='bitget' AND a.mode='bitget_demo' AND a.currency='USDT'
        FOR SHARE OF a;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    -- Explicit projection, including only an internal ownership check.
    -- Paused/disconnected and revoked remain visible; never invent a free slot.
    SELECT c.user_id,c.connection_id,c.credential_revision,c.storage_version,c.status
        INTO connection_row FROM platform.demo_credential_connections c
        WHERE c.tenant_id=actor.tenant_id AND c.platform_account_id=p_account FOR SHARE OF c;
    IF FOUND AND connection_row.user_id<>actor.user_id THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN jsonb_build_object(
        'tenant_id',actor.tenant_id,'auth_epoch',actor.auth_epoch,
        'purpose','demo_read_only','profile','bitget-classic-demo-read-secret/1','environment','demo',
        'account',jsonb_build_object('id',account_row.id,'name',account_row.name,
            'broker',account_row.broker,'mode',account_row.mode,'currency',account_row.currency,
            'status',account_row.status),
        'connection',CASE WHEN connection_row.connection_id IS NULL THEN NULL ELSE
            jsonb_build_object('connection_id',connection_row.connection_id,
                'credential_revision',connection_row.credential_revision,
                'storage_version',connection_row.storage_version,'status',connection_row.status) END);
END $$;
REVOKE ALL ON FUNCTION platform.demo_credential_action_context(uuid,bigint,bigint)
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION platform.demo_credential_action_context(uuid,bigint,bigint)
    TO investalo_runtime;
