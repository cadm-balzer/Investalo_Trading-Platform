-- Additive metadata boundary for the trusted API, never a credential read path.
-- The API verifies signed assertions and supplies transaction-local GUCs.
-- These GUCs are NOT an owner-bound credential LOGIN or an MFA authorization.
-- Migration 003/004 private tables and worker functions retain their grants/RLS.
CREATE FUNCTION platform.credential_action_context(p_account uuid)
RETURNS TABLE(
    tenant_id uuid,auth_epoch bigint,
    account_id uuid,account_name text,account_broker text,account_mode text,account_status text,
    connection_id uuid,credential_revision bigint,storage_version bigint,connection_status text
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
    context_tenant uuid; context_user uuid; current_epoch bigint;
    account_row record; connection_row record;
BEGIN
    -- SESSION_USER remains the authenticated runtime LOGIN inside this definer.
    IF SESSION_USER<>'investalo_runtime'
       OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname=SESSION_USER
            AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
            AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    BEGIN
        context_tenant:=NULLIF(pg_catalog.current_setting('app.tenant_id',true),'')::uuid;
        context_user:=NULLIF(pg_catalog.current_setting('app.user_id',true),'')::uuid;
    EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END;
    IF context_tenant IS NULL OR context_user IS NULL OR p_account IS NULL THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    SELECT u.auth_epoch INTO current_epoch
        FROM platform.users u JOIN platform.memberships m ON m.user_id=u.id
        WHERE u.id=context_user AND u.active
          AND u.oidc_issuer=pg_catalog.current_setting('app.oidc_issuer',true)
          AND u.oidc_subject=pg_catalog.current_setting('app.oidc_subject',true)
          AND m.tenant_id=context_tenant AND m.active AND m.role IN ('owner','trader')
        FOR SHARE OF u,m;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    -- Paused accounts must remain visible so a fresh revoke can be prepared.
    SELECT a.id,a.name,a.broker,a.mode,a.status INTO account_row
        FROM platform.accounts a WHERE a.tenant_id=context_tenant AND a.id=p_account
          AND a.broker='bitget' AND a.mode='read_only' FOR SHARE OF a;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    -- Never fetch a broker UID, parent UID, key ID or envelope, even internally.
    SELECT c.user_id,c.connection_id,c.credential_revision,c.storage_version,c.status
        INTO connection_row FROM platform.credential_connections c
        WHERE c.tenant_id=context_tenant AND c.platform_account_id=p_account FOR SHARE OF c;
    IF FOUND AND connection_row.user_id<>context_user THEN
        -- A tenant peer cannot discover another user's connection or see it as
        -- an available registration slot. Missing/foreign accounts also use 42501.
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN QUERY SELECT context_tenant,current_epoch,
        account_row.id,account_row.name,account_row.broker,account_row.mode,account_row.status,
        connection_row.connection_id,connection_row.credential_revision,
        connection_row.storage_version,connection_row.status;
END $$;
REVOKE ALL ON FUNCTION platform.credential_action_context(uuid)
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION platform.credential_action_context(uuid) TO investalo_runtime;
