-- Own Demo consent ledger and entry functions. No normal grant conversion.
-- Shared006/007 factor/counter/claim clocks remain unchanged; no executor/HTTP.
-- Explicit purpose consent, separate from 007 verification-only confirmation.
-- Trusted BFF verifies WebAuthn; trusted Python verifies the signed 30-claim
-- assertion and exact request bytes. SQL owns durable issuance and one-use state.
-- No credential executor, HTTP route, broker call or runtime activation is added.
CREATE TABLE platform.demo_passkey_credential_authorizations (
    authorization_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    proof_id uuid NOT NULL UNIQUE REFERENCES platform.passkey_action_proofs(proof_id),
    kind text NOT NULL DEFAULT 'passkey-demo-credential-authorization/1'
        CHECK(kind='passkey-demo-credential-authorization/1'),
    origin text NOT NULL,
    metadata_sha256 text NOT NULL CHECK(metadata_sha256~'^[0-9a-f]{64}$'),
    body_sha256 text NOT NULL CHECK(body_sha256~'^[0-9a-f]{64}$'),
    state text NOT NULL DEFAULT 'prepared' CHECK(state IN ('prepared','authorized','consumed','locked')),
    receipt jsonb,
    consumed_claims jsonb,
    consumed_jti uuid UNIQUE,
    consumed_by name,
    consumed_at bigint,
    consume_transaction xid8,
    locked_at bigint,
    lock_transaction xid8,
    CHECK(authorization_id<>proof_id),
    CHECK((state='prepared' AND receipt IS NULL AND consumed_claims IS NULL
           AND consumed_jti IS NULL AND consumed_by IS NULL AND consumed_at IS NULL
           AND consume_transaction IS NULL AND locked_at IS NULL AND lock_transaction IS NULL)
       OR (state IN ('authorized','consumed','locked') AND receipt IS NOT NULL AND jsonb_typeof(receipt)='object'
           AND ((state='authorized' AND consumed_claims IS NULL AND consumed_jti IS NULL
                 AND consumed_by IS NULL AND consumed_at IS NULL AND consume_transaction IS NULL
                 AND locked_at IS NULL AND lock_transaction IS NULL)
             OR (state IN ('consumed','locked') AND consumed_claims IS NOT NULL AND jsonb_typeof(consumed_claims)='object'
                 AND consumed_jti IS NOT NULL AND consumed_by IS NOT NULL AND consumed_at IS NOT NULL
                 AND consume_transaction IS NOT NULL
                 AND ((state='consumed' AND locked_at IS NULL AND lock_transaction IS NULL)
                   OR (state='locked' AND locked_at IS NOT NULL AND lock_transaction IS NOT NULL
                       AND lock_transaction<>consume_transaction))))))
);
CREATE TABLE platform.demo_passkey_credential_authorization_audit (
    authorization_id uuid NOT NULL REFERENCES platform.demo_passkey_credential_authorizations(authorization_id),
    event text NOT NULL CHECK(event IN ('prepared','authorized','consumed','locked')),
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    database_role name NOT NULL DEFAULT SESSION_USER,
    transaction_id xid8 NOT NULL DEFAULT pg_current_xact_id(),
    PRIMARY KEY(authorization_id,event)
);
ALTER TABLE platform.demo_passkey_credential_authorizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.demo_passkey_credential_authorizations FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.demo_passkey_credential_authorization_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.demo_passkey_credential_authorization_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY migration_management ON platform.demo_passkey_credential_authorizations
    TO investalo_migration USING(true) WITH CHECK(true);
CREATE POLICY migration_management ON platform.demo_passkey_credential_authorization_audit
    TO investalo_migration USING(true) WITH CHECK(true);
REVOKE ALL ON platform.demo_passkey_credential_authorizations,platform.demo_passkey_credential_authorization_audit
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;

CREATE FUNCTION platform.guard_demo_passkey_credential_authorization()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    ELSIF TG_OP='INSERT' THEN
        IF NEW.state<>'prepared' THEN RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023'; END IF;
    ELSE
        IF (OLD.authorization_id,OLD.proof_id,OLD.kind,OLD.origin,OLD.metadata_sha256,OLD.body_sha256)
           IS DISTINCT FROM
           (NEW.authorization_id,NEW.proof_id,NEW.kind,NEW.origin,NEW.metadata_sha256,NEW.body_sha256)
           OR NOT ((OLD.state='prepared' AND NEW.state='authorized')
             OR (OLD.state='authorized' AND NEW.state='consumed'
                 AND OLD.receipt IS NOT DISTINCT FROM NEW.receipt
                 AND NEW.consume_transaction=pg_current_xact_id() AND NEW.consumed_by=SESSION_USER)
             OR (OLD.state='consumed' AND NEW.state='locked'
                 AND (OLD.receipt,OLD.consumed_claims,OLD.consumed_jti,OLD.consumed_by,
                      OLD.consumed_at,OLD.consume_transaction) IS NOT DISTINCT FROM
                     (NEW.receipt,NEW.consumed_claims,NEW.consumed_jti,NEW.consumed_by,
                      NEW.consumed_at,NEW.consume_transaction)
                 AND NEW.lock_transaction=pg_current_xact_id()
                 AND NEW.lock_transaction<>OLD.consume_transaction)) THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_passkey_credential_authorization BEFORE INSERT OR UPDATE OR DELETE
    ON platform.demo_passkey_credential_authorizations FOR EACH ROW
    EXECUTE FUNCTION platform.guard_demo_passkey_credential_authorization();
CREATE TRIGGER passkey_credential_authorization_no_truncate BEFORE TRUNCATE
    ON platform.demo_passkey_credential_authorizations FOR EACH STATEMENT
    EXECUTE FUNCTION platform.guard_demo_passkey_credential_authorization();
CREATE TRIGGER immutable_demo_passkey_credential_authorization_audit BEFORE UPDATE OR DELETE
    ON platform.demo_passkey_credential_authorization_audit FOR EACH ROW
    EXECUTE FUNCTION platform.reject_credential_audit_mutation();
CREATE TRIGGER demo_passkey_credential_authorization_audit_no_truncate BEFORE TRUNCATE
    ON platform.demo_passkey_credential_authorization_audit FOR EACH STATEMENT
    EXECUTE FUNCTION platform.reject_credential_audit_mutation();


CREATE FUNCTION platform.demo_credential_passkey_metadata(p_tenant uuid,p_user uuid,p_epoch bigint,
    p_account uuid,p_action text)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE a record; c record;
BEGIN
    IF p_action IS NULL OR p_action NOT IN ('register','revoke') THEN
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
    SELECT x.user_id,x.connection_id,x.credential_revision,x.storage_version,x.status INTO c
        FROM platform.demo_credential_connections x WHERE x.tenant_id=p_tenant AND x.platform_account_id=p_account
        FOR UPDATE OF x;
    IF FOUND AND c.user_id<>p_user THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    RETURN jsonb_build_object('tenant_id',p_tenant,'auth_epoch',p_epoch,
        'purpose','demo_read_only','profile','bitget-classic-demo-read-secret/1','environment','demo',
        'account',jsonb_build_object('id',a.id,'name',a.name,'broker',a.broker,'mode',a.mode,'currency',a.currency,'status',a.status),
        'connection',CASE WHEN c.connection_id IS NULL THEN NULL ELSE
            jsonb_build_object('connection_id',c.connection_id,'credential_revision',c.credential_revision,
                'storage_version',c.storage_version,'status',c.status) END);
END $$;

CREATE FUNCTION platform.demo_passkey_action_locked(p_proof uuid,p_rp text,p_binding bytea,
    p_epoch bigint,p_oidc_auth_time bigint)
RETURNS platform.passkey_action_proofs
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; item platform.passkey_action_proofs%ROWTYPE; metadata_now jsonb; key_row record;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    PERFORM platform.passkey_rp(p_rp);
    IF p_proof IS NULL OR p_binding IS NULL OR octet_length(p_binding)<>32 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT r.* INTO item FROM platform.passkey_action_proofs r WHERE r.proof_id=p_proof
        AND r.tenant_id=actor.tenant_id AND r.user_id=actor.user_id
        AND r.rp_id=p_rp AND r.session_binding=p_binding;
    IF NOT FOUND OR item.metadata->>'purpose' IS DISTINCT FROM 'demo_read_only'
       OR item.metadata->>'profile' IS DISTINCT FROM 'bitget-classic-demo-read-secret/1'
       OR item.auth_epoch<>actor.auth_epoch OR item.oidc_issuer<>actor.oidc_issuer
       OR item.oidc_subject<>actor.oidc_subject OR item.oidc_auth_time<>p_oidc_auth_time THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    PERFORM platform.passkey_slot(actor.tenant_id,actor.user_id,p_rp);
    -- Registration has no connection row to lock. Its existing account row
    -- is the durable slot: 014 registration writers first take its SHARE
    -- lock, so UPDATE here excludes an insertion through the missing-row gap.
    IF item.target->>'action'='register' THEN
        PERFORM 1 FROM platform.accounts a WHERE a.tenant_id=actor.tenant_id
            AND a.id=item.platform_account_id FOR UPDATE OF a;
        IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    END IF;
    metadata_now:=platform.demo_credential_passkey_metadata(actor.tenant_id,actor.user_id,actor.auth_epoch,item.platform_account_id,item.target->>'action');
    SELECT r.* INTO STRICT item FROM platform.passkey_action_proofs r WHERE r.proof_id=p_proof FOR UPDATE OF r;
    IF metadata_now IS DISTINCT FROM item.metadata THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF item.target->>'action'='register' AND EXISTS(
        SELECT 1 FROM platform.demo_credential_connections c WHERE c.tenant_id=item.tenant_id
          AND c.connection_id=(item.target->>'connection_id')::uuid) THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    SELECT c.* INTO key_row FROM platform.passkey_credentials c WHERE c.passkey_id=item.passkey_id
        AND c.tenant_id=actor.tenant_id AND c.user_id=actor.user_id AND c.rp_id=p_rp FOR SHARE OF c;
    IF NOT FOUND OR key_row.status<>'active' OR key_row.enrollment_epoch<>actor.auth_epoch
       OR key_row.oidc_issuer<>actor.oidc_issuer OR key_row.oidc_subject<>actor.oidc_subject THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF key_row.storage_version<>(CASE WHEN item.state IN ('granted','confirmed')
        THEN item.passkey_version ELSE item.passkey_storage END) THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    PERFORM platform.passkey_action_clock(item);
    RETURN item;
END $$;

CREATE FUNCTION platform.demo_passkey_action_prepare(p_account uuid,p_action text,p_new_connection uuid,
    p_rp text,p_challenge bytea,p_session_binding bytea,p_confirmation_hash bytea,
    p_session_expires bigint,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_action_attempt_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; metadata_now jsonb; target_now jsonb; key_row record;
    issued_clock bigint; item platform.passkey_action_proofs%ROWTYPE;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    PERFORM platform.passkey_rp(p_rp);
    IF p_account IS NULL OR p_action IS NULL OR p_action NOT IN ('register','revoke')
       OR (p_action='register' AND p_new_connection IS NULL)
       OR (p_action<>'register' AND p_new_connection IS NOT NULL)
       OR p_challenge IS NULL OR octet_length(p_challenge)<>32
       OR p_session_binding IS NULL OR octet_length(p_session_binding)<>32
       OR p_confirmation_hash IS NULL OR octet_length(p_confirmation_hash)<>32
       OR p_session_expires IS NULL OR p_session_expires NOT BETWEEN 1 AND 9007199254740991 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    PERFORM platform.passkey_slot(actor.tenant_id,actor.user_id,p_rp);
    IF p_action='register' THEN
        PERFORM 1 FROM platform.accounts a WHERE a.tenant_id=actor.tenant_id AND a.id=p_account FOR UPDATE OF a;
        IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    END IF;
    metadata_now:=platform.demo_credential_passkey_metadata(actor.tenant_id,actor.user_id,actor.auth_epoch,p_account,p_action);
    IF p_action='register' THEN
        IF metadata_now->'connection'<>'null'::jsonb OR metadata_now->'account'->>'status'<>'ready' THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
        -- Never reuse any connection UUID already reserved in this tenant.
        IF EXISTS(SELECT 1 FROM platform.demo_credential_connections c
            WHERE c.tenant_id=actor.tenant_id AND c.connection_id=p_new_connection) THEN
            RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
        END IF;
        target_now:=jsonb_build_object('action',p_action,'platform_account_id',p_account,
            'connection_id',p_new_connection);
    ELSE
        IF metadata_now->'connection'='null'::jsonb
           OR metadata_now->'connection'->>'status'<>'active'
           OR (metadata_now->'connection'->>'credential_revision')::bigint>9007199254740991
           OR (metadata_now->'connection'->>'storage_version')::bigint>=9007199254740991 THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
        target_now:=jsonb_build_object('action',p_action,'platform_account_id',p_account,
            'connection_id',metadata_now->'connection'->>'connection_id',
            'expected_revision',(metadata_now->'connection'->>'credential_revision')::bigint,
            'expected_storage',(metadata_now->'connection'->>'storage_version')::bigint);
    END IF;
    SELECT c.* INTO key_row FROM platform.passkey_credentials c
        WHERE c.tenant_id=actor.tenant_id AND c.user_id=actor.user_id AND c.rp_id=p_rp FOR SHARE OF c;
    IF NOT FOUND OR key_row.status<>'active' OR key_row.enrollment_epoch<>actor.auth_epoch
       OR key_row.oidc_issuer<>actor.oidc_issuer OR key_row.oidc_subject<>actor.oidc_subject
       OR key_row.storage_version>=9007199254740991 THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    issued_clock:=floor(extract(epoch FROM clock_timestamp()))::bigint;
    IF p_session_expires<=issued_clock THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    IF (SELECT count(*) FROM platform.passkey_action_proofs r
        WHERE r.tenant_id=actor.tenant_id AND r.user_id=actor.user_id AND r.rp_id=p_rp
          AND ((r.state IN ('prepared','claimed') AND r.expires_at>issued_clock)
            OR (r.state='granted' AND r.grant_expires_at>issued_clock)))>=8 THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    INSERT INTO platform.passkey_action_proofs
        (tenant_id,user_id,rp_id,oidc_issuer,oidc_subject,oidc_auth_time,auth_epoch,
         target,metadata,platform_account_id,passkey_id,passkey_storage,
         session_binding,challenge,confirmation_hash,prepared_at,expires_at,session_expires_at)
        VALUES(actor.tenant_id,actor.user_id,p_rp,actor.oidc_issuer,actor.oidc_subject,p_oidc_auth_time,
               actor.auth_epoch,target_now,metadata_now,p_account,key_row.passkey_id,key_row.storage_version,
               p_session_binding,p_challenge,p_confirmation_hash,issued_clock,
               least(issued_clock+120,p_session_expires),p_session_expires)
        RETURNING * INTO item;
    INSERT INTO platform.passkey_action_audit
        (proof_id,event,tenant_id,user_id,rp_id,auth_epoch,passkey_id,passkey_version)
        VALUES(item.proof_id,'prepared',item.tenant_id,item.user_id,item.rp_id,item.auth_epoch,
               item.passkey_id,item.passkey_storage);
    PERFORM platform.passkey_action_clock(item);
    RETURN QUERY SELECT * FROM platform.passkey_action_attempt_view(item);
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
END $$;

CREATE FUNCTION platform.demo_passkey_action_claim(p_proof uuid,p_rp text,p_binding bytea,
    p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_action_attempt_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE item platform.passkey_action_proofs%ROWTYPE; claim_clock bigint;
BEGIN
    item:=platform.demo_passkey_action_locked(p_proof,p_rp,p_binding,p_epoch,p_oidc_auth_time);
    IF item.state<>'prepared' THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    claim_clock:=floor(extract(epoch FROM clock_timestamp()))::bigint;
    IF claim_clock>=item.expires_at THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    UPDATE platform.passkey_action_proofs r SET state='claimed',
        claimed_at=claim_clock,claim_transaction=pg_current_xact_id()
        WHERE r.proof_id=p_proof RETURNING r.* INTO item;
    INSERT INTO platform.passkey_action_audit
        (proof_id,event,tenant_id,user_id,rp_id,auth_epoch,passkey_id,passkey_version)
        VALUES(item.proof_id,'claimed',item.tenant_id,item.user_id,item.rp_id,item.auth_epoch,
               item.passkey_id,item.passkey_storage);
    PERFORM platform.passkey_action_clock(item);
    RETURN QUERY SELECT * FROM platform.passkey_action_attempt_view(item);
END $$;

CREATE FUNCTION platform.demo_passkey_action_finish(p_proof uuid,p_rp text,p_binding bytea,
    p_new_counter bigint,p_backup_eligible boolean,p_backed_up boolean,p_checked_at bigint,
    p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_action_grant_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE item platform.passkey_action_proofs%ROWTYPE; key_row record; grant_clock bigint;
BEGIN
    item:=platform.demo_passkey_action_locked(p_proof,p_rp,p_binding,p_epoch,p_oidc_auth_time);
    IF item.state<>'claimed' OR item.claim_transaction=pg_current_xact_id() THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF p_new_counter IS NULL OR p_new_counter NOT BETWEEN 0 AND 4294967295
       OR p_backup_eligible IS NULL OR p_backed_up IS NULL
       OR (p_backed_up AND NOT p_backup_eligible) OR p_checked_at IS NULL
       OR p_checked_at NOT BETWEEN 1 AND 9007199254740991 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT c.* INTO STRICT key_row FROM platform.passkey_credentials c WHERE c.passkey_id=item.passkey_id;
    grant_clock:=floor(extract(epoch FROM clock_timestamp()))::bigint;
    IF p_backup_eligible<>key_row.backup_eligible OR p_checked_at<item.claimed_at
       OR p_checked_at>=item.expires_at OR p_checked_at<grant_clock-120
       OR p_checked_at>grant_clock+5 THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    -- Counter/version/audit and the grant transition commit together.
    PERFORM * FROM platform.passkey_assertion_cas(item.passkey_id,item.passkey_storage,
        p_new_counter,p_backed_up,p_epoch,p_oidc_auth_time);
    grant_clock:=floor(extract(epoch FROM clock_timestamp()))::bigint;
    PERFORM platform.passkey_action_clock(item);
    UPDATE platform.passkey_action_proofs r SET state='granted',grant_id=gen_random_uuid(),
        passkey_version=item.passkey_storage+1,checked_at=p_checked_at,granted_at=grant_clock,
        grant_expires_at=least(grant_clock+120,p_checked_at+120,item.session_expires_at)
        WHERE r.proof_id=p_proof RETURNING r.* INTO item;
    INSERT INTO platform.passkey_action_audit
        (proof_id,event,tenant_id,user_id,rp_id,auth_epoch,passkey_id,passkey_version)
        VALUES(item.proof_id,'granted',item.tenant_id,item.user_id,item.rp_id,item.auth_epoch,
               item.passkey_id,item.passkey_version);
    PERFORM platform.passkey_action_clock(item);
    RETURN QUERY SELECT * FROM platform.passkey_action_grant_view(item);
END $$;

CREATE FUNCTION platform.demo_passkey_action_read_grant(p_grant uuid,p_rp text,p_binding bytea,
    p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_action_grant_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; proof uuid; item platform.passkey_action_proofs%ROWTYPE;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    SELECT r.proof_id INTO proof FROM platform.passkey_action_proofs r WHERE r.grant_id=p_grant
        AND r.tenant_id=actor.tenant_id AND r.user_id=actor.user_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    item:=platform.demo_passkey_action_locked(proof,p_rp,p_binding,p_epoch,p_oidc_auth_time);
    IF item.state<>'granted' THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    PERFORM platform.passkey_action_clock(item);
    RETURN QUERY SELECT * FROM platform.passkey_action_grant_view(item);
END $$;

CREATE FUNCTION platform.demo_passkey_action_confirm(p_grant uuid,p_rp text,p_binding bytea,
    p_confirmation_hash bytea,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_action_grant_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; proof uuid; item platform.passkey_action_proofs%ROWTYPE; confirm_clock bigint;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    IF p_confirmation_hash IS NULL OR octet_length(p_confirmation_hash)<>32 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT r.proof_id INTO proof FROM platform.passkey_action_proofs r WHERE r.grant_id=p_grant
        AND r.tenant_id=actor.tenant_id AND r.user_id=actor.user_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    item:=platform.demo_passkey_action_locked(proof,p_rp,p_binding,p_epoch,p_oidc_auth_time);
    IF item.state<>'granted' OR item.confirmation_hash<>p_confirmation_hash THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    confirm_clock:=floor(extract(epoch FROM clock_timestamp()))::bigint;
    IF confirm_clock>=item.grant_expires_at THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    UPDATE platform.passkey_action_proofs r SET state='confirmed',
        confirmed_at=confirm_clock
        WHERE r.proof_id=proof RETURNING r.* INTO item;
    INSERT INTO platform.passkey_action_audit
        (proof_id,event,tenant_id,user_id,rp_id,auth_epoch,passkey_id,passkey_version)
        VALUES(item.proof_id,'confirmed',item.tenant_id,item.user_id,item.rp_id,item.auth_epoch,
               item.passkey_id,item.passkey_version);
    PERFORM platform.passkey_action_clock(item);
    RETURN QUERY SELECT * FROM platform.passkey_action_grant_view(item);
END $$;

CREATE FUNCTION platform.demo_passkey_credential_prepare(p_account uuid,p_action text,p_new_connection uuid,
    p_rp text,p_origin text,p_challenge bytea,p_binding bytea,p_confirmation_hash bytea,
    p_body_sha256 text,p_session_expires bigint,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_credential_attempt_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE attempt platform.passkey_action_attempt_receipt; purpose platform.demo_passkey_credential_authorizations%ROWTYPE;
    proof platform.passkey_action_proofs%ROWTYPE;
BEGIN
    PERFORM platform.passkey_credential_origin(p_origin,p_rp);
    IF p_body_sha256 IS NULL OR p_body_sha256!~'^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT * INTO STRICT attempt FROM platform.demo_passkey_action_prepare(p_account,p_action,p_new_connection,
        p_rp,p_challenge,p_binding,p_confirmation_hash,p_session_expires,p_epoch,p_oidc_auth_time);
    SELECT r.* INTO STRICT proof FROM platform.passkey_action_proofs r WHERE r.proof_id=attempt.attempt_id;
    PERFORM platform.passkey_credential_origin(proof.oidc_issuer,
        substring(proof.oidc_issuer FROM '^https://([a-z0-9.-]+)'));
    IF octet_length(convert_to(proof.oidc_subject,'UTF8')) NOT BETWEEN 1 AND 255
       OR proof.oidc_subject~'[[:cntrl:]]' THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    INSERT INTO platform.demo_passkey_credential_authorizations(proof_id,origin,metadata_sha256,body_sha256)
        VALUES(attempt.attempt_id,p_origin,encode(sha256(convert_to(attempt.metadata::text,'UTF8')),'hex'),p_body_sha256)
        RETURNING * INTO purpose;
    INSERT INTO platform.demo_passkey_credential_authorization_audit(authorization_id,event)
        VALUES(purpose.authorization_id,'prepared');
    SELECT r.* INTO STRICT proof FROM platform.passkey_action_proofs r WHERE r.proof_id=attempt.attempt_id;
    PERFORM platform.passkey_action_clock(proof);
    RETURN QUERY SELECT purpose.authorization_id,attempt.*,purpose.metadata_sha256;
END $$;

CREATE FUNCTION platform.demo_passkey_credential_receipt(p_auth platform.demo_passkey_credential_authorizations,
    p_proof platform.passkey_action_proofs)
RETURNS jsonb LANGUAGE sql SET search_path=pg_catalog AS $$
    SELECT jsonb_build_object('kind',(p_auth).kind,'authorization_id',(p_auth).authorization_id,
        'proof_id',(p_proof).proof_id,'grant_id',(p_proof).grant_id,'tenant_id',(p_proof).tenant_id,
        'user_id',(p_proof).user_id,'subject',(p_proof).oidc_subject,'auth_epoch',(p_proof).auth_epoch,
        'oidc_issuer',(p_proof).oidc_issuer,'oidc_auth_time',(p_proof).oidc_auth_time,
        'rp_id',(p_proof).rp_id,'origin',(p_auth).origin,'session_binding',encode((p_proof).session_binding,'hex'),
        'session_expires_at',(p_proof).session_expires_at,'passkey_id',(p_proof).passkey_id,
        'passkey_version',(p_proof).passkey_version,'target',(p_proof).target,
        'prepared_at',(p_proof).prepared_at,'checked_at',(p_proof).checked_at,
        'authorized_at',(p_proof).confirmed_at,'expires_at',(p_proof).grant_expires_at,
        'metadata_sha256',(p_auth).metadata_sha256,'body_sha256',(p_auth).body_sha256);
$$;

CREATE FUNCTION platform.demo_passkey_credential_authorize(p_authorization uuid,p_grant uuid,
    p_rp text,p_origin text,p_binding bytea,p_confirmation_hash bytea,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE purpose platform.demo_passkey_credential_authorizations%ROWTYPE;
    proof platform.passkey_action_proofs%ROWTYPE; result jsonb; current_seconds bigint;
BEGIN
    SELECT a.* INTO purpose FROM platform.demo_passkey_credential_authorizations a WHERE a.authorization_id=p_authorization;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    proof:=platform.demo_passkey_action_locked(purpose.proof_id,p_rp,p_binding,p_epoch,p_oidc_auth_time);
    SELECT a.* INTO STRICT purpose FROM platform.demo_passkey_credential_authorizations a
        WHERE a.authorization_id=p_authorization FOR UPDATE OF a;
    IF purpose.state<>'prepared' OR proof.state<>'granted' OR proof.grant_id IS DISTINCT FROM p_grant
       OR purpose.origin IS DISTINCT FROM p_origin OR proof.confirmation_hash IS DISTINCT FROM p_confirmation_hash
       OR purpose.authorization_id IN (proof.proof_id,proof.grant_id) OR proof.proof_id=proof.grant_id
       OR proof.checked_at>floor(extract(epoch FROM clock_timestamp()))::bigint THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    PERFORM * FROM platform.demo_passkey_action_confirm(p_grant,p_rp,p_binding,p_confirmation_hash,p_epoch,p_oidc_auth_time);
    SELECT r.* INTO STRICT proof FROM platform.passkey_action_proofs r WHERE r.proof_id=purpose.proof_id;
    current_seconds:=floor(extract(epoch FROM clock_timestamp()))::bigint;
    IF proof.checked_at>proof.confirmed_at OR proof.confirmed_at>current_seconds
       OR proof.grant_expires_at<=current_seconds OR proof.session_expires_at<=current_seconds THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    result:=platform.demo_passkey_credential_receipt(purpose,proof);
    UPDATE platform.demo_passkey_credential_authorizations a SET state='authorized',receipt=result
        WHERE a.authorization_id=p_authorization;
    INSERT INTO platform.demo_passkey_credential_authorization_audit(authorization_id,event)
        VALUES(p_authorization,'authorized');
    PERFORM platform.passkey_action_clock(proof);
    current_seconds:=floor(extract(epoch FROM clock_timestamp()))::bigint;
    IF proof.confirmed_at>current_seconds OR proof.grant_expires_at<=current_seconds THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN result;
END $$;

CREATE FUNCTION platform.demo_passkey_credential_claims_valid(p_claims jsonb)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE field text; number_value numeric; target jsonb; action text;
BEGIN
    IF p_claims IS NULL OR jsonb_typeof(p_claims)<>'object' OR octet_length(p_claims::text)>8192 THEN RETURN false; END IF;
    IF (SELECT count(*) FROM jsonb_object_keys(p_claims))<>30 OR NOT p_claims ?& ARRAY[
        'iss','aud','sub','authorization_kind','authorization_id','proof_id','grant_id','tenant_id','user_id',
        'auth_epoch','oidc_iss','oidc_auth_time','rp_id','origin','session_binding','session_expires_at','passkey_id',
        'passkey_version','passkey_started_at','passkey_checked_at','passkey_authorized_at','authorization_expires_at',
        'metadata_sha256','target','iat','exp','jti','htm','htu','body_sha256'] THEN RETURN false; END IF;
    FOREACH field IN ARRAY ARRAY['iss','aud','sub','authorization_kind','authorization_id','proof_id','grant_id',
        'tenant_id','user_id','oidc_iss','rp_id','origin','session_binding','passkey_id','metadata_sha256','jti','htm','htu','body_sha256'] LOOP
        IF jsonb_typeof(p_claims->field)<>'string' THEN RETURN false; END IF;
    END LOOP;
    FOREACH field IN ARRAY ARRAY['authorization_id','proof_id','grant_id','tenant_id','user_id','passkey_id','jti'] LOOP
        IF p_claims->>field!~'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN RETURN false; END IF;
    END LOOP;
    IF p_claims->>'authorization_id' IN (p_claims->>'proof_id',p_claims->>'grant_id')
       OR p_claims->>'proof_id'=p_claims->>'grant_id' THEN RETURN false; END IF;
    FOREACH field IN ARRAY ARRAY['session_binding','metadata_sha256','body_sha256'] LOOP
        IF p_claims->>field!~'^[0-9a-f]{64}$' THEN RETURN false; END IF;
    END LOOP;
    FOREACH field IN ARRAY ARRAY['auth_epoch','oidc_auth_time','session_expires_at','passkey_version',
        'passkey_started_at','passkey_checked_at','passkey_authorized_at','authorization_expires_at','iat','exp'] LOOP
        IF jsonb_typeof(p_claims->field)<>'number' OR p_claims->>field!~'^(0|[1-9][0-9]*)$' THEN RETURN false; END IF;
        number_value:=(p_claims->>field)::numeric;
        IF number_value>9007199254740991 OR (field<>'auth_epoch' AND number_value<1)
           OR (field='passkey_version' AND number_value<2) THEN RETURN false; END IF;
    END LOOP;
    target:=p_claims->'target';
    IF jsonb_typeof(target)<>'object' THEN RETURN false; END IF;
    action:=target->>'action';
    IF action IS NULL OR action NOT IN ('register','revoke')
       OR jsonb_typeof(target->'action')<>'string'
       OR NOT target ?& ARRAY['action','platform_account_id','connection_id']
       OR (SELECT count(*) FROM jsonb_object_keys(target))<>(CASE WHEN action='register' THEN 3 ELSE 5 END) THEN RETURN false; END IF;
    FOREACH field IN ARRAY ARRAY['platform_account_id','connection_id'] LOOP
        IF jsonb_typeof(target->field)<>'string'
           OR target->>field!~'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN RETURN false; END IF;
    END LOOP;
    IF action<>'register' THEN
        IF NOT target ?& ARRAY['expected_revision','expected_storage'] THEN RETURN false; END IF;
        FOREACH field IN ARRAY ARRAY['expected_revision','expected_storage'] LOOP
            IF jsonb_typeof(target->field)<>'number' OR target->>field!~'^[1-9][0-9]*$' THEN RETURN false; END IF;
            number_value:=(target->>field)::numeric;
            IF number_value>9007199254740991 OR (field='expected_storage' AND number_value>=9007199254740991)
               OR (field='expected_revision' AND number_value<>1) THEN RETURN false; END IF;
        END LOOP;
    END IF;
    IF p_claims->>'iss'<>'investalo-bff' OR p_claims->>'aud'<>'investalo-credentials-demo-passkey'
       OR p_claims->>'authorization_kind'<>'passkey-demo-credential-authorization/1'
       OR p_claims->>'htm'<>'POST' OR p_claims->>'htu'<>'/v1/credentials/bitget-demo/'||action
       OR octet_length(convert_to(p_claims->>'sub','UTF8')) NOT BETWEEN 1 AND 255
       OR p_claims->>'sub'~'[[:cntrl:]]' THEN RETURN false; END IF;
    PERFORM platform.passkey_credential_origin(p_claims->>'origin',p_claims->>'rp_id');
    PERFORM platform.passkey_credential_origin(p_claims->>'oidc_iss',
        substring(p_claims->>'oidc_iss' FROM '^https://([a-z0-9.-]+)'));
    RETURN true;
EXCEPTION WHEN data_exception THEN RETURN false;
END $$;

CREATE FUNCTION platform.demo_credential_passkey_authorization_locked(p_claims jsonb)
RETURNS platform.demo_passkey_credential_authorizations
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; u record; proof platform.passkey_action_proofs%ROWTYPE;
    purpose platform.demo_passkey_credential_authorizations%ROWTYPE; metadata_now jsonb; key_row record;
BEGIN
    IF NOT platform.demo_passkey_credential_claims_valid(p_claims) THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT * INTO STRICT actor FROM platform.credential_context();
    SELECT x.* INTO STRICT u FROM platform.users x WHERE x.id=actor.user_id;
    IF actor.tenant_id::text<>p_claims->>'tenant_id' OR actor.user_id::text<>p_claims->>'user_id'
       OR u.auth_epoch<>(p_claims->>'auth_epoch')::bigint OR u.oidc_issuer<>p_claims->>'oidc_iss'
       OR u.oidc_subject<>p_claims->>'sub' OR extract(epoch FROM u.reauth_after)>(p_claims->>'oidc_auth_time')::bigint THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    SELECT a.* INTO purpose FROM platform.demo_passkey_credential_authorizations a
        WHERE a.authorization_id=(p_claims->>'authorization_id')::uuid;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    SELECT r.* INTO proof FROM platform.passkey_action_proofs r WHERE r.proof_id=purpose.proof_id
        AND r.tenant_id=actor.tenant_id AND r.user_id=actor.user_id;
    IF NOT FOUND OR proof.rp_id<>p_claims->>'rp_id' THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    PERFORM platform.passkey_slot(actor.tenant_id,actor.user_id,proof.rp_id);
    metadata_now:=platform.demo_credential_passkey_metadata(actor.tenant_id,actor.user_id,u.auth_epoch,
        proof.platform_account_id,proof.target->>'action');
    SELECT r.* INTO STRICT proof FROM platform.passkey_action_proofs r WHERE r.proof_id=purpose.proof_id FOR UPDATE OF r;
    IF metadata_now IS DISTINCT FROM proof.metadata THEN RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001'; END IF;
    IF proof.target->>'action'='register' AND EXISTS(SELECT 1 FROM platform.demo_credential_connections c
        WHERE c.tenant_id=actor.tenant_id AND c.connection_id=(proof.target->>'connection_id')::uuid) THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    SELECT x.* INTO key_row FROM platform.passkey_credentials x WHERE x.passkey_id=proof.passkey_id
        AND x.tenant_id=actor.tenant_id AND x.user_id=actor.user_id AND x.rp_id=proof.rp_id FOR SHARE OF x;
    IF NOT FOUND OR key_row.status<>'active' OR key_row.enrollment_epoch<>u.auth_epoch
       OR key_row.oidc_issuer<>u.oidc_issuer OR key_row.oidc_subject<>u.oidc_subject THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF key_row.storage_version IS DISTINCT FROM proof.passkey_version THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    SELECT a.* INTO STRICT purpose FROM platform.demo_passkey_credential_authorizations a
        WHERE a.authorization_id=(p_claims->>'authorization_id')::uuid FOR UPDATE OF a;
    IF proof.state<>'confirmed' OR purpose.state='prepared'
       OR purpose.receipt IS DISTINCT FROM platform.demo_passkey_credential_receipt(purpose,proof)
       OR purpose.receipt IS DISTINCT FROM platform.passkey_credential_claims_receipt(p_claims) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    PERFORM platform.passkey_credential_claims_clock(p_claims);
    RETURN purpose;
END $$;

CREATE FUNCTION platform.demo_credential_consume_passkey_authorization(p_claims jsonb)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE purpose platform.demo_passkey_credential_authorizations%ROWTYPE;
BEGIN
    purpose:=platform.demo_credential_passkey_authorization_locked(p_claims);
    IF purpose.state<>'authorized' THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    PERFORM platform.passkey_credential_claims_clock(p_claims);
    UPDATE platform.demo_passkey_credential_authorizations a SET state='consumed',consumed_claims=p_claims,
        consumed_jti=(p_claims->>'jti')::uuid,consumed_by=SESSION_USER,
        consumed_at=floor(extract(epoch FROM clock_timestamp()))::bigint,consume_transaction=pg_current_xact_id()
        WHERE a.authorization_id=purpose.authorization_id;
    INSERT INTO platform.demo_passkey_credential_authorization_audit(authorization_id,event)
        VALUES(purpose.authorization_id,'consumed');
    PERFORM platform.passkey_credential_claims_clock(p_claims);
    RETURN purpose.authorization_id;
EXCEPTION WHEN unique_violation THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
END $$;

CREATE FUNCTION platform.demo_credential_lock_passkey_authorization(p_claims jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE purpose platform.demo_passkey_credential_authorizations%ROWTYPE;
BEGIN
    purpose:=platform.demo_credential_passkey_authorization_locked(p_claims);
    IF purpose.state NOT IN ('consumed','locked') OR purpose.consume_transaction=pg_current_xact_id()
       OR purpose.consumed_by<>SESSION_USER OR purpose.consumed_claims IS DISTINCT FROM p_claims
       OR (purpose.state='locked' AND purpose.lock_transaction<>pg_current_xact_id()) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    PERFORM platform.passkey_credential_claims_clock(p_claims);
    IF purpose.state='consumed' THEN
        UPDATE platform.demo_passkey_credential_authorizations a SET state='locked',
            locked_at=floor(extract(epoch FROM clock_timestamp()))::bigint,lock_transaction=pg_current_xact_id()
            WHERE a.authorization_id=purpose.authorization_id;
        INSERT INTO platform.demo_passkey_credential_authorization_audit(authorization_id,event)
            VALUES(purpose.authorization_id,'locked');
    END IF;
    PERFORM platform.passkey_credential_claims_clock(p_claims);
    RETURN true;
END $$;

REVOKE ALL ON FUNCTION
 platform.guard_demo_passkey_credential_authorization(),
 platform.demo_credential_passkey_metadata(uuid,uuid,bigint,uuid,text),
 platform.demo_passkey_action_locked(uuid,text,bytea,bigint,bigint),
 platform.demo_passkey_action_prepare(uuid,text,uuid,text,bytea,bytea,bytea,bigint,bigint,bigint),
 platform.demo_passkey_action_claim(uuid,text,bytea,bigint,bigint),
 platform.demo_passkey_action_finish(uuid,text,bytea,bigint,boolean,boolean,bigint,bigint,bigint),
 platform.demo_passkey_action_read_grant(uuid,text,bytea,bigint,bigint),
 platform.demo_passkey_action_confirm(uuid,text,bytea,bytea,bigint,bigint),
 platform.demo_passkey_credential_prepare(uuid,text,uuid,text,text,bytea,bytea,bytea,text,bigint,bigint,bigint),
 platform.demo_passkey_credential_receipt(platform.demo_passkey_credential_authorizations,platform.passkey_action_proofs),
 platform.demo_passkey_credential_authorize(uuid,uuid,text,text,bytea,bytea,bigint,bigint),
 platform.demo_passkey_credential_claims_valid(jsonb),
 platform.demo_credential_passkey_authorization_locked(jsonb),
 platform.demo_credential_consume_passkey_authorization(jsonb),
 platform.demo_credential_lock_passkey_authorization(jsonb)
 FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION
 platform.demo_passkey_credential_prepare(uuid,text,uuid,text,text,bytea,bytea,bytea,text,bigint,bigint,bigint),
 platform.demo_passkey_credential_authorize(uuid,uuid,text,text,bytea,bytea,bigint,bigint),
 platform.demo_passkey_action_claim(uuid,text,bytea,bigint,bigint),
 platform.demo_passkey_action_finish(uuid,text,bytea,bigint,boolean,boolean,bigint,bigint,bigint),
 platform.demo_passkey_action_read_grant(uuid,text,bytea,bigint,bigint)
 TO investalo_runtime;
GRANT EXECUTE ON FUNCTION platform.demo_credential_consume_passkey_authorization(jsonb),
 platform.demo_credential_lock_passkey_authorization(jsonb) TO investalo_credentials_worker;
