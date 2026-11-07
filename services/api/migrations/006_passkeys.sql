-- Durable public-key registry for a trusted API, not browser authentication.
-- Runtime GUCs/p_epoch/auth_time are verified assertions supplied by the API.
-- SQL does not verify WebAuthn, invitation delivery, UV or a fresh factor.
-- Enrollment claim MUST commit before cryptographic verification. Assertion
-- challenge consumption remains a caller requirement, separate from counter CAS.
CREATE TABLE platform.passkey_credentials (
    passkey_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    rp_id text NOT NULL CHECK(length(rp_id) BETWEEN 1 AND 253),
    credential_id bytea NOT NULL CHECK(octet_length(credential_id) BETWEEN 1 AND 1023),
    user_handle bytea NOT NULL CHECK(octet_length(user_handle)=32),
    public_key bytea NOT NULL CHECK(octet_length(public_key) BETWEEN 1 AND 2048),
    oidc_issuer text NOT NULL,
    oidc_subject text NOT NULL,
    enrollment_epoch bigint NOT NULL CHECK(enrollment_epoch BETWEEN 0 AND 9007199254740991),
    sign_count bigint NOT NULL CHECK(sign_count BETWEEN 0 AND 4294967295),
    backup_eligible boolean NOT NULL,
    backed_up boolean NOT NULL,
    storage_version bigint NOT NULL DEFAULT 1 CHECK(storage_version BETWEEN 1 AND 9007199254740991),
    status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','revoked')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    revoked_at timestamptz,
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id),
    UNIQUE(tenant_id,user_id,rp_id),
    UNIQUE(rp_id,credential_id),
    CHECK(NOT backed_up OR backup_eligible),
    CHECK((status='active' AND revoked_at IS NULL) OR (status='revoked' AND revoked_at IS NOT NULL))
);
CREATE TABLE platform.passkey_enrollment_tickets (
    ticket_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    rp_id text NOT NULL,
    token_hash bytea NOT NULL UNIQUE CHECK(octet_length(token_hash)=32),
    user_handle bytea NOT NULL CHECK(octet_length(user_handle)=32),
    auth_epoch bigint NOT NULL CHECK(auth_epoch BETWEEN 0 AND 9007199254740991),
    oidc_issuer text NOT NULL,
    oidc_subject text NOT NULL,
    confirmation_reference uuid NOT NULL,
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    state text NOT NULL DEFAULT 'issued' CHECK(state IN ('issued','claimed','finished')),
    claim_id uuid UNIQUE,
    session_binding bytea,
    claimed_at timestamptz,
    claim_expires_at timestamptz,
    claim_transaction xid8,
    finished_at timestamptz,
    passkey_id uuid REFERENCES platform.passkey_credentials(passkey_id),
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id),
    CHECK(expires_at>issued_at AND expires_at<=issued_at+interval '600 seconds'),
    CHECK((state='issued' AND claim_id IS NULL AND session_binding IS NULL
           AND claimed_at IS NULL AND claim_expires_at IS NULL AND claim_transaction IS NULL
           AND finished_at IS NULL AND passkey_id IS NULL)
       OR (state IN ('claimed','finished') AND claim_id IS NOT NULL
           AND session_binding IS NOT NULL AND octet_length(session_binding)=32
           AND claimed_at IS NOT NULL AND claim_expires_at IS NOT NULL
           AND claim_expires_at>claimed_at AND claim_expires_at<=claimed_at+interval '120 seconds'
           AND claim_expires_at<=expires_at AND claim_transaction IS NOT NULL
           AND ((state='claimed' AND finished_at IS NULL AND passkey_id IS NULL)
             OR (state='finished' AND finished_at IS NOT NULL AND passkey_id IS NOT NULL))))
);
CREATE TABLE platform.passkey_audit (
    audit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    rp_id text NOT NULL,
    event text NOT NULL CHECK(event IN ('issued','claimed','enrolled','asserted','revoked')),
    ticket_id uuid REFERENCES platform.passkey_enrollment_tickets(ticket_id),
    passkey_id uuid REFERENCES platform.passkey_credentials(passkey_id),
    storage_version bigint,
    auth_epoch bigint NOT NULL,
    confirmation_reference uuid,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id)
);
ALTER TABLE platform.passkey_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.passkey_credentials FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.passkey_enrollment_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.passkey_enrollment_tickets FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.passkey_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.passkey_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY migration_management ON platform.passkey_credentials
    TO investalo_migration USING(true) WITH CHECK(true);
CREATE POLICY migration_management ON platform.passkey_enrollment_tickets
    TO investalo_migration USING(true) WITH CHECK(true);
CREATE POLICY migration_management ON platform.passkey_audit
    TO investalo_migration USING(true) WITH CHECK(true);
REVOKE ALL ON platform.passkey_credentials,platform.passkey_enrollment_tickets,platform.passkey_audit
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;

CREATE FUNCTION platform.guard_passkey_credential()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    ELSIF TG_OP='INSERT' THEN
        IF NEW.storage_version<>1 OR NEW.status<>'active' OR NEW.revoked_at IS NOT NULL THEN
            RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
        END IF;
    ELSE
        IF OLD.status<>'active' OR OLD.storage_version=9007199254740991
           OR NEW.storage_version<>OLD.storage_version+1
           OR (OLD.passkey_id,OLD.tenant_id,OLD.user_id,OLD.rp_id,OLD.credential_id,
               OLD.user_handle,OLD.public_key,OLD.oidc_issuer,OLD.oidc_subject,
               OLD.enrollment_epoch,OLD.backup_eligible,OLD.created_at)
              IS DISTINCT FROM
              (NEW.passkey_id,NEW.tenant_id,NEW.user_id,NEW.rp_id,NEW.credential_id,
               NEW.user_handle,NEW.public_key,NEW.oidc_issuer,NEW.oidc_subject,
               NEW.enrollment_epoch,NEW.backup_eligible,NEW.created_at)
           OR (NEW.status='active' AND NOT
               (NEW.sign_count>OLD.sign_count OR (NEW.sign_count=0 AND OLD.sign_count=0)))
           OR (NEW.status='revoked' AND
               (NEW.sign_count,NEW.backed_up) IS DISTINCT FROM (OLD.sign_count,OLD.backed_up)) THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_passkey_credential BEFORE INSERT OR UPDATE OR DELETE
    ON platform.passkey_credentials FOR EACH ROW EXECUTE FUNCTION platform.guard_passkey_credential();
CREATE TRIGGER passkey_credential_no_truncate BEFORE TRUNCATE
    ON platform.passkey_credentials FOR EACH STATEMENT EXECUTE FUNCTION platform.guard_passkey_credential();

CREATE FUNCTION platform.guard_passkey_ticket()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    ELSIF TG_OP='INSERT' THEN
        IF NEW.state<>'issued' THEN RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023'; END IF;
    ELSE
        IF (OLD.ticket_id,OLD.tenant_id,OLD.user_id,OLD.rp_id,OLD.token_hash,OLD.user_handle,
            OLD.auth_epoch,OLD.oidc_issuer,OLD.oidc_subject,OLD.confirmation_reference,OLD.issued_at,OLD.expires_at)
           IS DISTINCT FROM
           (NEW.ticket_id,NEW.tenant_id,NEW.user_id,NEW.rp_id,NEW.token_hash,NEW.user_handle,
            NEW.auth_epoch,NEW.oidc_issuer,NEW.oidc_subject,NEW.confirmation_reference,NEW.issued_at,NEW.expires_at)
           OR NOT ((OLD.state='issued' AND NEW.state='claimed')
                OR (OLD.state='claimed' AND NEW.state='finished'
                    AND (OLD.claim_id,OLD.session_binding,OLD.claimed_at,OLD.claim_expires_at,OLD.claim_transaction)
                        IS NOT DISTINCT FROM
                        (NEW.claim_id,NEW.session_binding,NEW.claimed_at,NEW.claim_expires_at,NEW.claim_transaction))) THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_passkey_ticket BEFORE INSERT OR UPDATE OR DELETE
    ON platform.passkey_enrollment_tickets FOR EACH ROW EXECUTE FUNCTION platform.guard_passkey_ticket();
CREATE TRIGGER passkey_ticket_no_truncate BEFORE TRUNCATE
    ON platform.passkey_enrollment_tickets FOR EACH STATEMENT EXECUTE FUNCTION platform.guard_passkey_ticket();
CREATE TRIGGER immutable_passkey_audit BEFORE UPDATE OR DELETE
    ON platform.passkey_audit FOR EACH ROW EXECUTE FUNCTION platform.reject_credential_audit_mutation();
CREATE TRIGGER passkey_audit_no_truncate BEFORE TRUNCATE
    ON platform.passkey_audit FOR EACH STATEMENT EXECUTE FUNCTION platform.reject_credential_audit_mutation();

CREATE FUNCTION platform.passkey_rp(p_rp text)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF p_rp IS NULL OR length(p_rp) NOT BETWEEN 1 AND 253
       OR p_rp !~ '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$'
       OR (strpos(p_rp,'.')=0 AND p_rp<>'localhost') OR p_rp~'^[0-9.]+$' THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
END $$;
CREATE FUNCTION platform.passkey_slot(p_tenant uuid,p_user uuid,p_rp text)
RETURNS void LANGUAGE sql SET search_path=pg_catalog AS $$
    SELECT pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(p_tenant::text||'/'||p_user::text||'/'||p_rp,0));
$$;

-- Only the trusted runtime LOGIN may assert API identity. SET ROLE is not
-- sufficient. These helpers are private; the API cannot call them independently.
CREATE FUNCTION platform.passkey_actor(p_epoch bigint,p_oidc_auth_time bigint)
RETURNS TABLE(tenant_id uuid,user_id uuid,oidc_issuer text,oidc_subject text,auth_epoch bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE context_tenant uuid; context_user uuid;
BEGIN
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
    IF context_tenant IS NULL OR context_user IS NULL OR p_epoch IS NULL
       OR p_epoch NOT BETWEEN 0 AND 9007199254740991 OR p_oidc_auth_time IS NULL
       OR p_oidc_auth_time NOT BETWEEN 1 AND 9007199254740991
       OR p_oidc_auth_time>floor(extract(epoch FROM clock_timestamp()))::bigint+5 THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN QUERY SELECT m.tenant_id,u.id,u.oidc_issuer,u.oidc_subject,u.auth_epoch
        FROM platform.users u JOIN platform.memberships m ON m.user_id=u.id
        WHERE u.id=context_user AND u.active AND u.auth_epoch=p_epoch
          AND u.oidc_issuer=pg_catalog.current_setting('app.oidc_issuer',true)
          AND u.oidc_subject=pg_catalog.current_setting('app.oidc_subject',true)
          AND p_oidc_auth_time>=extract(epoch FROM u.reauth_after)
          AND m.tenant_id=context_tenant AND m.active AND m.role IN ('owner','trader')
        FOR SHARE OF u,m;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
END $$;

CREATE FUNCTION platform.passkey_issue_enrollment(p_tenant uuid,p_user uuid,p_rp text,
    p_token_hash bytea,p_user_handle bytea,p_epoch bigint,p_expires_at timestamptz,p_confirmation uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE user_row platform.users%ROWTYPE; issued uuid; issued_clock timestamptz;
BEGIN
    IF SESSION_USER<>'investalo_migration' THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    PERFORM platform.passkey_rp(p_rp);
    IF p_tenant IS NULL OR p_user IS NULL OR p_token_hash IS NULL OR octet_length(p_token_hash)<>32
       OR p_user_handle IS NULL OR octet_length(p_user_handle)<>32 OR p_confirmation IS NULL
       OR p_epoch IS NULL OR p_epoch NOT BETWEEN 0 AND 9007199254740991
       OR p_expires_at IS NULL OR NOT isfinite(p_expires_at) THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT u.* INTO user_row FROM platform.users u JOIN platform.memberships m ON m.user_id=u.id
        WHERE u.id=p_user AND u.active AND u.auth_epoch=p_epoch AND m.tenant_id=p_tenant
          AND m.active AND m.role IN ('owner','trader') FOR SHARE OF u,m;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    PERFORM platform.passkey_slot(p_tenant,p_user,p_rp);
    issued_clock:=clock_timestamp();
    IF p_expires_at<=issued_clock OR p_expires_at>issued_clock+interval '600 seconds' THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF EXISTS(SELECT 1 FROM platform.passkey_credentials c
        WHERE c.tenant_id=p_tenant AND c.user_id=p_user AND c.rp_id=p_rp)
       OR EXISTS(SELECT 1 FROM platform.passkey_enrollment_tickets t
        WHERE t.tenant_id=p_tenant AND t.user_id=p_user AND t.rp_id=p_rp
          AND t.expires_at>issued_clock AND
              (t.state='issued' OR (t.state='claimed' AND t.claim_expires_at>issued_clock))) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    INSERT INTO platform.passkey_enrollment_tickets
        (tenant_id,user_id,rp_id,token_hash,user_handle,auth_epoch,oidc_issuer,oidc_subject,
         confirmation_reference,issued_at,expires_at)
        VALUES(p_tenant,p_user,p_rp,p_token_hash,p_user_handle,p_epoch,user_row.oidc_issuer,user_row.oidc_subject,
               p_confirmation,issued_clock,p_expires_at)
        RETURNING ticket_id INTO issued;
    INSERT INTO platform.passkey_audit(tenant_id,user_id,rp_id,event,ticket_id,auth_epoch,confirmation_reference)
        VALUES(p_tenant,p_user,p_rp,'issued',issued,p_epoch,p_confirmation);
    IF p_expires_at<=clock_timestamp() THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN issued;
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
END $$;

CREATE FUNCTION platform.passkey_claim_enrollment(p_token_hash bytea,p_rp text,
    p_session_binding bytea,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS TABLE(claim_id uuid,user_handle bytea,expires_at timestamptz,tenant_id uuid,user_id uuid,auth_epoch bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; ticket platform.passkey_enrollment_tickets%ROWTYPE; claim_clock timestamptz; new_claim uuid;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    PERFORM platform.passkey_rp(p_rp);
    IF p_token_hash IS NULL OR octet_length(p_token_hash)<>32
       OR p_session_binding IS NULL OR octet_length(p_session_binding)<>32 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    PERFORM platform.passkey_slot(actor.tenant_id,actor.user_id,p_rp);
    SELECT t.* INTO ticket FROM platform.passkey_enrollment_tickets t
        WHERE t.token_hash=p_token_hash AND t.tenant_id=actor.tenant_id AND t.user_id=actor.user_id
          AND t.rp_id=p_rp AND t.auth_epoch=actor.auth_epoch AND t.state='issued' FOR UPDATE OF t;
    IF NOT FOUND OR ticket.expires_at<=clock_timestamp()
       OR ticket.oidc_issuer<>actor.oidc_issuer OR ticket.oidc_subject<>actor.oidc_subject
       OR EXISTS(SELECT 1 FROM platform.passkey_credentials c
        WHERE c.tenant_id=actor.tenant_id AND c.user_id=actor.user_id AND c.rp_id=p_rp) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    claim_clock:=clock_timestamp(); new_claim:=gen_random_uuid();
    UPDATE platform.passkey_enrollment_tickets t SET state='claimed',claim_id=new_claim,
        session_binding=p_session_binding,claimed_at=claim_clock,
        claim_expires_at=least(ticket.expires_at,claim_clock+interval '120 seconds'),
        claim_transaction=pg_current_xact_id() WHERE t.ticket_id=ticket.ticket_id;
    INSERT INTO platform.passkey_audit(tenant_id,user_id,rp_id,event,ticket_id,auth_epoch)
        VALUES(actor.tenant_id,actor.user_id,p_rp,'claimed',ticket.ticket_id,actor.auth_epoch);
    IF ticket.expires_at<=clock_timestamp() OR claim_clock+interval '120 seconds'<=clock_timestamp() THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN QUERY SELECT new_claim,ticket.user_handle,least(ticket.expires_at,claim_clock+interval '120 seconds'),
        actor.tenant_id,actor.user_id,actor.auth_epoch;
END $$;

CREATE FUNCTION platform.passkey_read(p_rp text,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS TABLE(passkey_id uuid,tenant_id uuid,user_id uuid,rp_id text,credential_id bytea,
    user_handle bytea,public_key bytea,sign_count bigint,backup_eligible boolean,backed_up boolean,
    storage_version bigint,status text,enrollment_epoch bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    PERFORM platform.passkey_rp(p_rp);
    PERFORM platform.passkey_slot(actor.tenant_id,actor.user_id,p_rp);
    RETURN QUERY SELECT c.passkey_id,c.tenant_id,c.user_id,c.rp_id,c.credential_id,c.user_handle,c.public_key,
        c.sign_count,c.backup_eligible,c.backed_up,c.storage_version,c.status,c.enrollment_epoch
        FROM platform.passkey_credentials c
        WHERE c.tenant_id=actor.tenant_id AND c.user_id=actor.user_id AND c.rp_id=p_rp FOR SHARE OF c;
END $$;

CREATE FUNCTION platform.passkey_finish_enrollment(p_claim_id uuid,p_session_binding bytea,
    p_credential_id bytea,p_public_key bytea,p_sign_count bigint,p_backup_eligible boolean,p_backed_up boolean,
    p_epoch bigint,p_oidc_auth_time bigint)
RETURNS TABLE(passkey_id uuid,tenant_id uuid,user_id uuid,rp_id text,credential_id bytea,
    user_handle bytea,public_key bytea,sign_count bigint,backup_eligible boolean,backed_up boolean,
    storage_version bigint,status text,enrollment_epoch bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; ticket platform.passkey_enrollment_tickets%ROWTYPE; inserted uuid; claim_rp text;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    IF p_claim_id IS NULL OR p_session_binding IS NULL OR octet_length(p_session_binding)<>32
       OR p_credential_id IS NULL OR octet_length(p_credential_id) NOT BETWEEN 1 AND 1023
       OR p_public_key IS NULL OR octet_length(p_public_key) NOT BETWEEN 1 AND 2048
       OR p_sign_count IS NULL OR p_sign_count NOT BETWEEN 0 AND 4294967295
       OR p_backup_eligible IS NULL OR p_backed_up IS NULL OR (p_backed_up AND NOT p_backup_eligible) THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT t.rp_id INTO claim_rp FROM platform.passkey_enrollment_tickets t
        WHERE t.claim_id=p_claim_id AND t.tenant_id=actor.tenant_id AND t.user_id=actor.user_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    PERFORM platform.passkey_slot(actor.tenant_id,actor.user_id,claim_rp);
    SELECT t.* INTO ticket FROM platform.passkey_enrollment_tickets t
        WHERE t.claim_id=p_claim_id AND t.tenant_id=actor.tenant_id AND t.user_id=actor.user_id FOR UPDATE OF t;
    IF NOT FOUND OR ticket.state<>'claimed' OR ticket.auth_epoch<>actor.auth_epoch
       OR ticket.oidc_issuer<>actor.oidc_issuer OR ticket.oidc_subject<>actor.oidc_subject
       OR ticket.session_binding<>p_session_binding OR ticket.claim_transaction=pg_current_xact_id()
       OR ticket.claim_expires_at<=clock_timestamp() OR ticket.expires_at<=clock_timestamp()
       OR EXISTS(SELECT 1 FROM platform.passkey_credentials c
           WHERE c.tenant_id=actor.tenant_id AND c.user_id=actor.user_id AND c.rp_id=ticket.rp_id) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    INSERT INTO platform.passkey_credentials AS inserted_row
        (tenant_id,user_id,rp_id,credential_id,user_handle,public_key,oidc_issuer,oidc_subject,
         enrollment_epoch,sign_count,backup_eligible,backed_up)
        VALUES(actor.tenant_id,actor.user_id,ticket.rp_id,p_credential_id,ticket.user_handle,p_public_key,
               actor.oidc_issuer,actor.oidc_subject,actor.auth_epoch,p_sign_count,p_backup_eligible,p_backed_up)
        RETURNING inserted_row.passkey_id INTO inserted;
    UPDATE platform.passkey_enrollment_tickets t SET state='finished',finished_at=clock_timestamp(),
        passkey_id=inserted WHERE t.ticket_id=ticket.ticket_id;
    INSERT INTO platform.passkey_audit(tenant_id,user_id,rp_id,event,ticket_id,passkey_id,storage_version,auth_epoch)
        VALUES(actor.tenant_id,actor.user_id,ticket.rp_id,'enrolled',ticket.ticket_id,inserted,1,actor.auth_epoch);
    IF ticket.claim_expires_at<=clock_timestamp() OR ticket.expires_at<=clock_timestamp() THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN QUERY SELECT * FROM platform.passkey_read(ticket.rp_id,p_epoch,p_oidc_auth_time);
    IF ticket.claim_expires_at<=clock_timestamp() OR ticket.expires_at<=clock_timestamp() THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
END $$;

CREATE FUNCTION platform.passkey_assertion_cas(p_passkey_id uuid,p_expected_storage bigint,
    p_new_counter bigint,p_backed_up boolean,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS TABLE(passkey_id uuid,tenant_id uuid,user_id uuid,rp_id text,credential_id bytea,
    user_handle bytea,public_key bytea,sign_count bigint,backup_eligible boolean,backed_up boolean,
    storage_version bigint,status text,enrollment_epoch bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; key_row platform.passkey_credentials%ROWTYPE; key_rp text;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    IF p_passkey_id IS NULL OR p_expected_storage IS NULL
       OR p_expected_storage NOT BETWEEN 1 AND 9007199254740990
       OR p_new_counter IS NULL OR p_new_counter NOT BETWEEN 0 AND 4294967295 OR p_backed_up IS NULL THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT c.rp_id INTO key_rp FROM platform.passkey_credentials c
        WHERE c.passkey_id=p_passkey_id AND c.tenant_id=actor.tenant_id AND c.user_id=actor.user_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    PERFORM platform.passkey_slot(actor.tenant_id,actor.user_id,key_rp);
    SELECT c.* INTO key_row FROM platform.passkey_credentials c WHERE c.passkey_id=p_passkey_id FOR UPDATE OF c;
    IF key_row.status<>'active' OR key_row.enrollment_epoch<>actor.auth_epoch
       OR key_row.oidc_issuer<>actor.oidc_issuer OR key_row.oidc_subject<>actor.oidc_subject
       OR (p_backed_up AND NOT key_row.backup_eligible) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF key_row.storage_version<>p_expected_storage THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF NOT (p_new_counter>key_row.sign_count OR (p_new_counter=0 AND key_row.sign_count=0)) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    UPDATE platform.passkey_credentials c SET sign_count=p_new_counter,backed_up=p_backed_up,
        storage_version=c.storage_version+1 WHERE c.passkey_id=p_passkey_id;
    INSERT INTO platform.passkey_audit(tenant_id,user_id,rp_id,event,passkey_id,storage_version,auth_epoch)
        VALUES(actor.tenant_id,actor.user_id,key_rp,'asserted',p_passkey_id,p_expected_storage+1,actor.auth_epoch);
    RETURN QUERY SELECT * FROM platform.passkey_read(key_rp,p_epoch,p_oidc_auth_time);
END $$;

-- Administrative revocation is also global user-session invalidation. It is not
-- a recovery/re-enrollment path; terminal rows and both unique constraints remain.
CREATE FUNCTION platform.passkey_admin_revoke(p_passkey_id uuid,p_expected_storage bigint,p_confirmation uuid)
RETURNS TABLE(passkey_id uuid,tenant_id uuid,user_id uuid,rp_id text,credential_id bytea,
    user_handle bytea,public_key bytea,sign_count bigint,backup_eligible boolean,backed_up boolean,
    storage_version bigint,status text,enrollment_epoch bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE key_row platform.passkey_credentials%ROWTYPE; key_owner uuid; next_epoch bigint;
BEGIN
    IF SESSION_USER<>'investalo_migration' THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF p_passkey_id IS NULL OR p_expected_storage IS NULL
       OR p_expected_storage NOT BETWEEN 1 AND 9007199254740990 OR p_confirmation IS NULL THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT c.user_id INTO key_owner FROM platform.passkey_credentials c WHERE c.passkey_id=p_passkey_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    SELECT u.auth_epoch+1 INTO next_epoch FROM platform.users u WHERE u.id=key_owner
        AND u.auth_epoch<9007199254740991 FOR UPDATE OF u;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    SELECT c.* INTO key_row FROM platform.passkey_credentials c WHERE c.passkey_id=p_passkey_id;
    PERFORM platform.passkey_slot(key_row.tenant_id,key_row.user_id,key_row.rp_id);
    SELECT c.* INTO key_row FROM platform.passkey_credentials c WHERE c.passkey_id=p_passkey_id FOR UPDATE OF c;
    IF key_row.status<>'active' THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    IF key_row.storage_version<>p_expected_storage THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    UPDATE platform.passkey_credentials c SET status='revoked',revoked_at=clock_timestamp(),
        storage_version=c.storage_version+1 WHERE c.passkey_id=p_passkey_id;
    UPDATE platform.users SET auth_epoch=next_epoch,reauth_after=clock_timestamp() WHERE id=key_owner;
    INSERT INTO platform.passkey_audit(tenant_id,user_id,rp_id,event,passkey_id,storage_version,auth_epoch,confirmation_reference)
        VALUES(key_row.tenant_id,key_owner,key_row.rp_id,'revoked',p_passkey_id,p_expected_storage+1,next_epoch,p_confirmation);
    RETURN QUERY SELECT c.passkey_id,c.tenant_id,c.user_id,c.rp_id,c.credential_id,c.user_handle,c.public_key,
        c.sign_count,c.backup_eligible,c.backed_up,c.storage_version,c.status,c.enrollment_epoch
        FROM platform.passkey_credentials c WHERE c.passkey_id=p_passkey_id;
END $$;

REVOKE ALL ON FUNCTION platform.guard_passkey_credential(),platform.guard_passkey_ticket(),
    platform.passkey_rp(text),platform.passkey_slot(uuid,uuid,text),platform.passkey_actor(bigint,bigint),
    platform.passkey_issue_enrollment(uuid,uuid,text,bytea,bytea,bigint,timestamptz,uuid),
    platform.passkey_claim_enrollment(bytea,text,bytea,bigint,bigint),
    platform.passkey_finish_enrollment(uuid,bytea,bytea,bytea,bigint,boolean,boolean,bigint,bigint),
    platform.passkey_read(text,bigint,bigint),
    platform.passkey_assertion_cas(uuid,bigint,bigint,boolean,bigint,bigint),
    platform.passkey_admin_revoke(uuid,bigint,uuid)
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION
    platform.passkey_claim_enrollment(bytea,text,bytea,bigint,bigint),
    platform.passkey_finish_enrollment(uuid,bytea,bytea,bytea,bigint,boolean,boolean,bigint,bigint),
    platform.passkey_read(text,bigint,bigint),
    platform.passkey_assertion_cas(uuid,bigint,bigint,boolean,bigint,bigint)
    TO investalo_runtime;
