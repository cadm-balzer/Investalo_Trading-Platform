-- Private worker read, authorized by an independently verified durable user
-- intent. requested_ms is the original authorization time, never an OIDC
-- auth_time. Existing browser/session/Passkey functions stay unchanged.
CREATE FUNCTION platform.demo_worker_credential_read(
    p_connection uuid, p_epoch bigint, p_subject text, p_issuer text,
    p_requested_ms bigint, p_revision bigint, p_storage bigint, p_lease_ms bigint)
RETURNS SETOF platform.demo_credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; u platform.users%ROWTYPE; now_ms bigint;
BEGIN
    SELECT * INTO STRICT actor FROM platform.credential_context();
    SELECT x.* INTO STRICT u FROM platform.users x WHERE x.id=actor.user_id FOR SHARE;
    now_ms:=floor(extract(epoch FROM clock_timestamp())*1000)::bigint;
    IF p_epoch IS NULL OR p_epoch<0 OR p_epoch<>u.auth_epoch
       OR p_subject IS NULL OR p_subject<>u.oidc_subject
       OR p_issuer IS NULL OR p_issuer<>u.oidc_issuer
       OR p_requested_ms IS NULL OR p_requested_ms<=0 OR p_requested_ms>now_ms+5000
       OR p_requested_ms<ceil(extract(epoch FROM u.reauth_after)*1000)
       OR p_revision IS NULL OR p_revision<>1
       OR p_storage IS NULL OR p_storage<1
       OR p_lease_ms IS NULL OR p_lease_ms<=now_ms OR p_lease_ms>now_ms+60000 THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN QUERY SELECT c.* FROM platform.demo_credential_connections c
        JOIN platform.accounts a ON a.tenant_id=c.tenant_id AND a.id=c.platform_account_id
        WHERE c.tenant_id=actor.tenant_id AND c.user_id=actor.user_id
          AND c.connection_id=p_connection AND c.status='active'
          AND c.credential_revision=p_revision AND c.storage_version=p_storage
          AND c.environment='demo' AND c.api_family='classic'
          AND c.profile='bitget-classic-demo-trading-secret/1'
          AND c.connection_mode='demo_futures_spot_trading'
          AND c.position_mode='one_way_mode' AND c.leverage=2
          AND platform.demo_trading_authorities_valid(c.authorities)
          AND a.broker='bitget' AND a.mode='bitget_demo'
          AND a.currency='USDT' AND a.status='ready'
        FOR SHARE OF c,a;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
END $$;

REVOKE ALL ON FUNCTION platform.demo_worker_credential_read(
    uuid,bigint,text,text,bigint,bigint,bigint,bigint)
    FROM PUBLIC,investalo_runtime,investalo_research_worker;
GRANT EXECUTE ON FUNCTION platform.demo_worker_credential_read(
    uuid,bigint,text,text,bigint,bigint,bigint,bigint) TO investalo_credentials_worker;
