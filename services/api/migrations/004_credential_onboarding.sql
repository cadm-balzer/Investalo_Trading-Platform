-- Additive request authorization for the trusted onboarding orchestrator.
-- JWT signature/audience/request-body binding and amr=mfa are verified in Python.
-- These functions do not wrap or change migration 003's trusted storage primitives.
CREATE TABLE platform.credential_onboarding_requests (
    jti uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    platform_account_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    action text NOT NULL CHECK(action IN ('register','replace','revoke')),
    expected_revision bigint,
    expected_storage bigint,
    oidc_issuer text NOT NULL,
    oidc_subject text NOT NULL,
    auth_epoch bigint NOT NULL CHECK(auth_epoch>=0),
    auth_time bigint NOT NULL CHECK(auth_time>0),
    started_at bigint NOT NULL CHECK(started_at>0),
    expires_at bigint NOT NULL CHECK(expires_at>0),
    state text NOT NULL DEFAULT 'authorized' CHECK(state IN ('authorized','completed','failed')),
    authorized_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    locked_transaction xid8,
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id),
    FOREIGN KEY(tenant_id,platform_account_id) REFERENCES platform.accounts(tenant_id,id),
    CHECK((action='register' AND expected_revision IS NULL AND expected_storage IS NULL)
       OR (action IN ('replace','revoke') AND expected_revision IS NOT NULL AND expected_storage IS NOT NULL
           AND expected_revision>0 AND expected_storage>0)),
    CHECK((state='authorized' AND finished_at IS NULL)
       OR (state IN ('completed','failed') AND finished_at IS NOT NULL))
);
CREATE TABLE platform.credential_onboarding_audit (
    jti uuid NOT NULL REFERENCES platform.credential_onboarding_requests(jti),
    event text NOT NULL CHECK(event IN ('authorized','completed','failed')),
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    platform_account_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    action text NOT NULL CHECK(action IN ('register','replace','revoke')),
    credential_revision bigint,
    storage_version bigint,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(jti,event),
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id),
    FOREIGN KEY(tenant_id,platform_account_id) REFERENCES platform.accounts(tenant_id,id)
);
ALTER TABLE platform.credential_onboarding_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.credential_onboarding_requests FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.credential_onboarding_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.credential_onboarding_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY migration_management ON platform.credential_onboarding_requests
    TO investalo_migration USING(true) WITH CHECK(true);
CREATE POLICY migration_management ON platform.credential_onboarding_audit
    TO investalo_migration USING(true) WITH CHECK(true);
REVOKE ALL ON platform.credential_onboarding_requests,platform.credential_onboarding_audit
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;

CREATE FUNCTION platform.guard_credential_request()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    ELSIF TG_OP='INSERT' THEN
        IF NEW.state<>'authorized' OR NEW.finished_at IS NOT NULL OR NEW.locked_transaction IS NOT NULL THEN
            RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
        END IF;
    ELSE
        IF OLD.state<>'authorized'
           OR (OLD.jti,OLD.tenant_id,OLD.user_id,OLD.platform_account_id,OLD.connection_id,
               OLD.action,OLD.expected_revision,OLD.expected_storage,OLD.oidc_issuer,OLD.oidc_subject,
               OLD.auth_epoch,OLD.auth_time,OLD.started_at,OLD.expires_at,OLD.authorized_at)
              IS DISTINCT FROM
              (NEW.jti,NEW.tenant_id,NEW.user_id,NEW.platform_account_id,NEW.connection_id,
               NEW.action,NEW.expected_revision,NEW.expected_storage,NEW.oidc_issuer,NEW.oidc_subject,
               NEW.auth_epoch,NEW.auth_time,NEW.started_at,NEW.expires_at,NEW.authorized_at)
           OR (NEW.state='authorized' AND NEW.finished_at IS NOT NULL)
           OR (NEW.state IN ('completed','failed') AND NEW.finished_at IS NULL)
           OR (NEW.state='completed' AND
               (OLD.locked_transaction IS DISTINCT FROM pg_current_xact_id()
                OR NEW.locked_transaction IS DISTINCT FROM OLD.locked_transaction)) THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_credential_request BEFORE INSERT OR UPDATE OR DELETE
    ON platform.credential_onboarding_requests FOR EACH ROW EXECUTE FUNCTION platform.guard_credential_request();
CREATE TRIGGER credential_request_no_truncate BEFORE TRUNCATE
    ON platform.credential_onboarding_requests FOR EACH STATEMENT EXECUTE FUNCTION platform.guard_credential_request();

CREATE FUNCTION platform.reject_credential_audit_mutation()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
END $$;
CREATE TRIGGER immutable_credential_audit BEFORE UPDATE OR DELETE
    ON platform.credential_onboarding_audit FOR EACH ROW EXECUTE FUNCTION platform.reject_credential_audit_mutation();
CREATE TRIGGER credential_audit_no_truncate BEFORE TRUNCATE
    ON platform.credential_onboarding_audit FOR EACH STATEMENT EXECUTE FUNCTION platform.reject_credential_audit_mutation();

CREATE FUNCTION platform.credential_request_clock(p_auth_time bigint,p_started_at bigint,p_expires_at bigint)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE now_seconds bigint := floor(extract(epoch FROM clock_timestamp()))::bigint;
BEGIN
    IF p_auth_time IS NULL OR p_started_at IS NULL OR p_expires_at IS NULL
       OR p_auth_time<=0 OR p_started_at<=0 OR p_expires_at<=0 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    -- The five-second allowance applies to future clock skew, never to an
    -- authentication predating the server-stored browser-bound step-up start.
    IF p_auth_time<p_started_at OR p_auth_time<now_seconds-120 OR p_auth_time>now_seconds+5
       OR p_started_at<now_seconds-300 OR p_started_at>now_seconds+5
       OR p_expires_at<=now_seconds OR p_expires_at>now_seconds+60 THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
END $$;

CREATE FUNCTION platform.credential_request_scope(p_tenant uuid,p_user uuid,p_action text,
    p_account uuid,p_connection uuid,p_revision bigint,p_storage bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE current_record platform.credential_connections%ROWTYPE;
BEGIN
    IF p_action IS NULL OR p_action NOT IN ('register','replace','revoke')
       OR p_account IS NULL OR p_connection IS NULL
       OR (p_action='register' AND (p_revision IS NOT NULL OR p_storage IS NOT NULL))
       OR (p_action IN ('replace','revoke') AND
           (p_revision IS NULL OR p_storage IS NULL OR p_revision<=0 OR p_storage<=0
            OR p_storage=9223372036854775807
            OR (p_action='replace' AND p_revision=9223372036854775807))) THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    PERFORM 1 FROM platform.accounts a WHERE a.tenant_id=p_tenant AND a.id=p_account
        AND (p_action='revoke' OR (a.broker='bitget' AND a.mode='read_only' AND a.status<>'paused'))
        FOR SHARE OF a;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    IF p_action='register' THEN
        PERFORM 1 FROM platform.credential_connections c
            WHERE c.tenant_id=p_tenant AND (c.connection_id=p_connection OR c.platform_account_id=p_account);
        IF FOUND THEN RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001'; END IF;
    ELSE
        SELECT c.* INTO current_record FROM platform.credential_connections c
            WHERE c.tenant_id=p_tenant AND c.user_id=p_user AND c.connection_id=p_connection
              AND c.platform_account_id=p_account AND c.status='active' FOR UPDATE OF c;
        IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
        IF current_record.credential_revision<>p_revision OR current_record.storage_version<>p_storage THEN
            RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
        END IF;
    END IF;
END $$;

CREATE FUNCTION platform.credential_request_identity(p_request platform.credential_onboarding_requests,
    p_require_fresh boolean)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE context_row record; user_row platform.users%ROWTYPE;
BEGIN
    SELECT * INTO STRICT context_row FROM platform.credential_context();
    IF context_row.tenant_id<>p_request.tenant_id OR context_row.user_id<>p_request.user_id THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF p_require_fresh THEN
        SELECT u.* INTO STRICT user_row FROM platform.users u WHERE u.id=context_row.user_id FOR SHARE OF u;
        IF user_row.oidc_issuer<>p_request.oidc_issuer OR user_row.oidc_subject<>p_request.oidc_subject
           OR user_row.auth_epoch<>p_request.auth_epoch THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
        PERFORM platform.credential_request_clock(p_request.auth_time,p_request.started_at,p_request.expires_at);
        IF to_timestamp(p_request.auth_time)<user_row.reauth_after THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
    END IF;
END $$;

CREATE FUNCTION platform.credential_begin_request(p_jti uuid,p_issuer text,p_subject text,p_epoch bigint,
    p_auth_time bigint,p_started_at bigint,p_expires_at bigint,p_action text,
    p_account uuid,p_connection uuid,p_expected_revision bigint,p_expected_storage bigint)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE context_row record; user_row platform.users%ROWTYPE; inserted uuid;
BEGIN
    SELECT * INTO STRICT context_row FROM platform.credential_context();
    IF p_jti IS NULL OR p_issuer IS NULL OR length(p_issuer) NOT BETWEEN 1 AND 2048
       OR p_subject IS NULL OR length(p_subject) NOT BETWEEN 1 AND 255
       OR p_epoch IS NULL OR p_epoch<0 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    PERFORM platform.credential_request_clock(p_auth_time,p_started_at,p_expires_at);
    SELECT u.* INTO STRICT user_row FROM platform.users u WHERE u.id=context_row.user_id FOR SHARE OF u;
    IF user_row.oidc_issuer<>p_issuer OR user_row.oidc_subject<>p_subject OR user_row.auth_epoch<>p_epoch
       OR to_timestamp(p_auth_time)<user_row.reauth_after THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF EXISTS(SELECT 1 FROM platform.credential_onboarding_requests WHERE jti=p_jti) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    PERFORM platform.credential_request_scope(context_row.tenant_id,context_row.user_id,p_action,
        p_account,p_connection,p_expected_revision,p_expected_storage);
    INSERT INTO platform.credential_onboarding_requests
        (jti,tenant_id,user_id,platform_account_id,connection_id,action,expected_revision,expected_storage,
         oidc_issuer,oidc_subject,auth_epoch,auth_time,started_at,expires_at)
        VALUES(p_jti,context_row.tenant_id,context_row.user_id,p_account,p_connection,p_action,
               p_expected_revision,p_expected_storage,user_row.oidc_issuer,user_row.oidc_subject,
               user_row.auth_epoch,p_auth_time,p_started_at,p_expires_at)
        ON CONFLICT(jti) DO NOTHING RETURNING jti INTO inserted;
    IF inserted IS NULL THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    INSERT INTO platform.credential_onboarding_audit
        (jti,event,tenant_id,user_id,platform_account_id,connection_id,action,credential_revision,storage_version)
        VALUES(p_jti,'authorized',context_row.tenant_id,context_row.user_id,p_account,p_connection,
               p_action,p_expected_revision,p_expected_storage);
    -- An account/context lock may have waited beyond the token's expiry.
    -- Never publish an expired grant to the subsequent broker-probe phase.
    PERFORM platform.credential_request_clock(p_auth_time,p_started_at,p_expires_at);
    RETURN inserted;
END $$;

CREATE FUNCTION platform.credential_lock_request(p_jti uuid,p_action text,p_account uuid,
    p_connection uuid,p_expected_revision bigint,p_expected_storage bigint)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE context_row record; request_row platform.credential_onboarding_requests%ROWTYPE;
BEGIN
    SELECT * INTO STRICT context_row FROM platform.credential_context();
    SELECT r.* INTO request_row FROM platform.credential_onboarding_requests r
        WHERE r.jti=p_jti AND r.tenant_id=context_row.tenant_id AND r.user_id=context_row.user_id
          AND r.state='authorized' FOR UPDATE OF r;
    IF NOT FOUND OR (request_row.action,request_row.platform_account_id,request_row.connection_id,
                    request_row.expected_revision,request_row.expected_storage)
                   IS DISTINCT FROM (p_action,p_account,p_connection,p_expected_revision,p_expected_storage) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    PERFORM platform.credential_request_identity(request_row,true);
    PERFORM platform.credential_request_scope(request_row.tenant_id,request_row.user_id,request_row.action,
        request_row.platform_account_id,request_row.connection_id,request_row.expected_revision,request_row.expected_storage);
    UPDATE platform.credential_onboarding_requests SET locked_transaction=pg_current_xact_id() WHERE jti=p_jti;
    PERFORM platform.credential_request_clock(request_row.auth_time,request_row.started_at,request_row.expires_at);
    RETURN true;
END $$;

CREATE FUNCTION platform.credential_finish_request(p_jti uuid,p_outcome text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE context_row record; request_row platform.credential_onboarding_requests%ROWTYPE;
        stored platform.credential_connections%ROWTYPE; final_revision bigint; final_storage bigint;
BEGIN
    SELECT * INTO STRICT context_row FROM platform.credential_context();
    IF p_outcome IS NULL OR p_outcome NOT IN ('completed','failed') THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT r.* INTO request_row FROM platform.credential_onboarding_requests r
        WHERE r.jti=p_jti AND r.tenant_id=context_row.tenant_id AND r.user_id=context_row.user_id
          AND r.state='authorized' FOR UPDATE OF r;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    -- Failure finalization records a consumed request after a rejected/timed-out
    -- probe or write rollback. It grants no write and needs no still-live token.
    PERFORM platform.credential_request_identity(request_row,p_outcome='completed');
    final_revision:=request_row.expected_revision;
    final_storage:=request_row.expected_storage;
    IF p_outcome='completed' THEN
        IF request_row.locked_transaction IS DISTINCT FROM pg_current_xact_id() THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
        PERFORM 1 FROM platform.accounts a WHERE a.tenant_id=request_row.tenant_id
            AND a.id=request_row.platform_account_id
            AND (request_row.action='revoke' OR (a.broker='bitget' AND a.mode='read_only' AND a.status<>'paused'))
            FOR SHARE OF a;
        IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
        SELECT c.* INTO stored FROM platform.credential_connections c
            WHERE c.tenant_id=request_row.tenant_id AND c.user_id=request_row.user_id
              AND c.connection_id=request_row.connection_id AND c.platform_account_id=request_row.platform_account_id
            FOR UPDATE OF c;
        IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
        IF request_row.action='register' THEN
            final_revision:=1; final_storage:=1;
        ELSIF request_row.action='replace' THEN
            final_revision:=request_row.expected_revision+1; final_storage:=request_row.expected_storage+1;
        ELSE
            final_storage:=request_row.expected_storage+1;
        END IF;
        IF stored.credential_revision<>final_revision OR stored.storage_version<>final_storage
           OR stored.status<>(CASE WHEN request_row.action='revoke' THEN 'revoked' ELSE 'active' END) THEN
            RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
        END IF;
    END IF;
    UPDATE platform.credential_onboarding_requests SET state=p_outcome,finished_at=clock_timestamp() WHERE jti=p_jti;
    INSERT INTO platform.credential_onboarding_audit
        (jti,event,tenant_id,user_id,platform_account_id,connection_id,action,credential_revision,storage_version)
        VALUES(p_jti,p_outcome,request_row.tenant_id,request_row.user_id,request_row.platform_account_id,
               request_row.connection_id,request_row.action,final_revision,final_storage);
    IF p_outcome='completed' THEN
        -- Check after every potentially blocking row/FK lock and immediately
        -- before returning to the transaction factory's commit boundary.
        PERFORM platform.credential_request_clock(request_row.auth_time,request_row.started_at,request_row.expires_at);
    END IF;
    RETURN true;
END $$;

REVOKE ALL ON FUNCTION platform.guard_credential_request(),platform.reject_credential_audit_mutation(),
    platform.credential_request_clock(bigint,bigint,bigint),
    platform.credential_request_scope(uuid,uuid,text,uuid,uuid,bigint,bigint),
    platform.credential_request_identity(platform.credential_onboarding_requests,boolean),
    platform.credential_begin_request(uuid,text,text,bigint,bigint,bigint,bigint,text,uuid,uuid,bigint,bigint),
    platform.credential_lock_request(uuid,text,uuid,uuid,bigint,bigint),
    platform.credential_finish_request(uuid,text)
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION
    platform.credential_begin_request(uuid,text,text,bigint,bigint,bigint,bigint,text,uuid,uuid,bigint,bigint),
    platform.credential_lock_request(uuid,text,uuid,uuid,bigint,bigint),
    platform.credential_finish_request(uuid,text) TO investalo_credentials_worker;
