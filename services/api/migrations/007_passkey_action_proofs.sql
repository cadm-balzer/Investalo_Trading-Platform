-- Verification-only target-bound passkey proofs for the trusted BFF/API.
-- SQL trusts WebAuthn verification, UV/UP and device eligibility checked in BFF.
-- This migration does NOT authorize credential writes, broker calls or live use.
-- Original OIDC authentication time remains distinct from passkey_checked_at.
CREATE TABLE platform.passkey_action_proofs (
    proof_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    rp_id text NOT NULL,
    oidc_issuer text NOT NULL,
    oidc_subject text NOT NULL,
    oidc_auth_time bigint NOT NULL,
    auth_epoch bigint NOT NULL CHECK(auth_epoch BETWEEN 0 AND 9007199254740991),
    target jsonb NOT NULL CHECK(jsonb_typeof(target)='object'),
    metadata jsonb NOT NULL CHECK(jsonb_typeof(metadata)='object'),
    platform_account_id uuid NOT NULL,
    passkey_id uuid NOT NULL REFERENCES platform.passkey_credentials(passkey_id),
    passkey_storage bigint NOT NULL CHECK(passkey_storage BETWEEN 1 AND 9007199254740990),
    session_binding bytea NOT NULL CHECK(octet_length(session_binding)=32),
    challenge bytea NOT NULL CHECK(octet_length(challenge)=32),
    confirmation_hash bytea NOT NULL CHECK(octet_length(confirmation_hash)=32),
    prepared_at bigint NOT NULL CHECK(prepared_at>0),
    expires_at bigint NOT NULL,
    session_expires_at bigint NOT NULL CHECK(session_expires_at BETWEEN 1 AND 9007199254740991),
    state text NOT NULL DEFAULT 'prepared' CHECK(state IN ('prepared','claimed','granted','confirmed')),
    claimed_at bigint,
    claim_transaction xid8,
    grant_id uuid UNIQUE,
    passkey_version bigint,
    checked_at bigint,
    granted_at bigint,
    grant_expires_at bigint,
    confirmed_at bigint,
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id),
    FOREIGN KEY(tenant_id,platform_account_id) REFERENCES platform.accounts(tenant_id,id),
    UNIQUE(rp_id,challenge),
    CHECK(oidc_auth_time BETWEEN 1 AND 9007199254740991),
    CHECK(expires_at>prepared_at AND expires_at<=prepared_at+120 AND expires_at<=session_expires_at),
    CHECK((state='prepared' AND claimed_at IS NULL AND claim_transaction IS NULL
           AND grant_id IS NULL AND passkey_version IS NULL AND checked_at IS NULL
           AND granted_at IS NULL AND grant_expires_at IS NULL AND confirmed_at IS NULL)
       OR (state IN ('claimed','granted','confirmed') AND claimed_at IS NOT NULL
           AND claimed_at>=prepared_at AND claimed_at<expires_at AND claim_transaction IS NOT NULL
           AND ((state='claimed' AND grant_id IS NULL AND passkey_version IS NULL
                 AND checked_at IS NULL AND granted_at IS NULL AND grant_expires_at IS NULL
                 AND confirmed_at IS NULL)
             OR (state IN ('granted','confirmed') AND grant_id IS NOT NULL
                 AND passkey_version=passkey_storage+1 AND checked_at IS NOT NULL
                 AND checked_at>=claimed_at AND checked_at<expires_at
                 AND granted_at IS NOT NULL AND granted_at>=claimed_at AND granted_at<expires_at
                 AND grant_expires_at IS NOT NULL AND grant_expires_at>granted_at
                 AND grant_expires_at<=granted_at+120 AND grant_expires_at<=checked_at+120
                 AND grant_expires_at<=session_expires_at
                 AND ((state='granted' AND confirmed_at IS NULL)
                   OR (state='confirmed' AND confirmed_at IS NOT NULL
                       AND confirmed_at>=granted_at AND confirmed_at<grant_expires_at))))))
);
CREATE INDEX passkey_action_live_by_actor ON platform.passkey_action_proofs(tenant_id,user_id,rp_id,state);
CREATE TABLE platform.passkey_action_audit (
    proof_id uuid NOT NULL REFERENCES platform.passkey_action_proofs(proof_id),
    event text NOT NULL CHECK(event IN ('prepared','claimed','granted','confirmed')),
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    rp_id text NOT NULL,
    auth_epoch bigint NOT NULL,
    passkey_id uuid NOT NULL REFERENCES platform.passkey_credentials(passkey_id),
    passkey_version bigint NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(proof_id,event),
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id)
);
ALTER TABLE platform.passkey_action_proofs ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.passkey_action_proofs FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.passkey_action_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.passkey_action_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY migration_management ON platform.passkey_action_proofs
    TO investalo_migration USING(true) WITH CHECK(true);
CREATE POLICY migration_management ON platform.passkey_action_audit
    TO investalo_migration USING(true) WITH CHECK(true);
REVOKE ALL ON platform.passkey_action_proofs,platform.passkey_action_audit
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;

CREATE FUNCTION platform.guard_passkey_action_proof()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    ELSIF TG_OP='INSERT' THEN
        IF NEW.state<>'prepared' THEN RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023'; END IF;
    ELSE
        IF (OLD.proof_id,OLD.tenant_id,OLD.user_id,OLD.rp_id,OLD.oidc_issuer,OLD.oidc_subject,
            OLD.oidc_auth_time,OLD.auth_epoch,OLD.target,OLD.metadata,OLD.platform_account_id,
            OLD.passkey_id,OLD.passkey_storage,OLD.session_binding,OLD.challenge,OLD.confirmation_hash,
            OLD.prepared_at,OLD.expires_at,OLD.session_expires_at)
           IS DISTINCT FROM
           (NEW.proof_id,NEW.tenant_id,NEW.user_id,NEW.rp_id,NEW.oidc_issuer,NEW.oidc_subject,
            NEW.oidc_auth_time,NEW.auth_epoch,NEW.target,NEW.metadata,NEW.platform_account_id,
            NEW.passkey_id,NEW.passkey_storage,NEW.session_binding,NEW.challenge,NEW.confirmation_hash,
            NEW.prepared_at,NEW.expires_at,NEW.session_expires_at)
           OR NOT ((OLD.state='prepared' AND NEW.state='claimed'
                     AND NEW.claim_transaction=pg_current_xact_id())
                OR (OLD.state='claimed' AND NEW.state='granted'
                    AND OLD.claim_transaction IS DISTINCT FROM pg_current_xact_id()
                    AND (OLD.claimed_at,OLD.claim_transaction)
                        IS NOT DISTINCT FROM (NEW.claimed_at,NEW.claim_transaction))
                OR (OLD.state='granted' AND NEW.state='confirmed'
                    AND (OLD.claimed_at,OLD.claim_transaction,OLD.grant_id,OLD.passkey_version,
                         OLD.checked_at,OLD.granted_at,OLD.grant_expires_at)
                        IS NOT DISTINCT FROM
                        (NEW.claimed_at,NEW.claim_transaction,NEW.grant_id,NEW.passkey_version,
                         NEW.checked_at,NEW.granted_at,NEW.grant_expires_at))) THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER immutable_passkey_action_proof BEFORE INSERT OR UPDATE OR DELETE
    ON platform.passkey_action_proofs FOR EACH ROW EXECUTE FUNCTION platform.guard_passkey_action_proof();
CREATE TRIGGER passkey_action_proof_no_truncate BEFORE TRUNCATE
    ON platform.passkey_action_proofs FOR EACH STATEMENT EXECUTE FUNCTION platform.guard_passkey_action_proof();
CREATE TRIGGER immutable_passkey_action_audit BEFORE UPDATE OR DELETE
    ON platform.passkey_action_audit FOR EACH ROW EXECUTE FUNCTION platform.reject_credential_audit_mutation();
CREATE TRIGGER passkey_action_audit_no_truncate BEFORE TRUNCATE
    ON platform.passkey_action_audit FOR EACH STATEMENT EXECUTE FUNCTION platform.reject_credential_audit_mutation();

CREATE TYPE platform.passkey_action_attempt_receipt AS (
    attempt_id uuid,tenant_id uuid,user_id uuid,auth_epoch bigint,rp_id text,
    target jsonb,metadata jsonb,passkey_id uuid,passkey_storage bigint,sign_count bigint,
    backup_eligible boolean,backed_up boolean,credential_id bytea,user_handle bytea,
    public_key bytea,enrollment_epoch bigint,session_binding bytea,challenge bytea,
    confirmation_hash bytea,prepared_at bigint,expires_at bigint,session_expires_at bigint
);
CREATE TYPE platform.passkey_action_grant_receipt AS (
    grant_id uuid,attempt_id uuid,tenant_id uuid,user_id uuid,auth_epoch bigint,rp_id text,
    target jsonb,metadata jsonb,passkey_id uuid,passkey_version bigint,session_binding bytea,
    confirmation_hash bytea,checked_at bigint,expires_at bigint,session_expires_at bigint
);

-- Only 005's safe metadata projection is used: no broker UID/envelope/key fetch.
CREATE FUNCTION platform.passkey_action_metadata(p_account uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE item record;
BEGIN
    SELECT * INTO STRICT item FROM platform.credential_action_context(p_account);
    RETURN jsonb_build_object(
        'tenant_id',item.tenant_id,'auth_epoch',item.auth_epoch,
        'account',jsonb_build_object('id',item.account_id,'name',item.account_name,
            'broker',item.account_broker,'mode',item.account_mode,'status',item.account_status),
        'connection',CASE WHEN item.connection_id IS NULL THEN NULL ELSE
            jsonb_build_object('connection_id',item.connection_id,'credential_revision',item.credential_revision,
                'storage_version',item.storage_version,'status',item.connection_status) END);
END $$;

CREATE FUNCTION platform.passkey_action_attempt_view(p_proof platform.passkey_action_proofs)
RETURNS SETOF platform.passkey_action_attempt_receipt
LANGUAGE sql SET search_path=pg_catalog AS $$
    SELECT (p_proof).proof_id,(p_proof).tenant_id,(p_proof).user_id,(p_proof).auth_epoch,(p_proof).rp_id,
        (p_proof).target,(p_proof).metadata,(p_proof).passkey_id,(p_proof).passkey_storage,c.sign_count,
        c.backup_eligible,c.backed_up,c.credential_id,c.user_handle,c.public_key,c.enrollment_epoch,
        (p_proof).session_binding,(p_proof).challenge,(p_proof).confirmation_hash,
        (p_proof).prepared_at,(p_proof).expires_at,(p_proof).session_expires_at
    FROM platform.passkey_credentials c WHERE c.passkey_id=(p_proof).passkey_id;
$$;
CREATE FUNCTION platform.passkey_action_grant_view(p_proof platform.passkey_action_proofs)
RETURNS SETOF platform.passkey_action_grant_receipt
LANGUAGE sql SET search_path=pg_catalog AS $$
    SELECT (p_proof).grant_id,(p_proof).proof_id,(p_proof).tenant_id,(p_proof).user_id,(p_proof).auth_epoch,
        (p_proof).rp_id,(p_proof).target,(p_proof).metadata,(p_proof).passkey_id,(p_proof).passkey_version,
        (p_proof).session_binding,(p_proof).confirmation_hash,(p_proof).checked_at,
        (p_proof).grant_expires_at,(p_proof).session_expires_at;
$$;

CREATE FUNCTION platform.passkey_action_clock(p_proof platform.passkey_action_proofs)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE current_seconds bigint:=floor(extract(epoch FROM clock_timestamp()))::bigint;
BEGIN
    IF p_proof.prepared_at>current_seconds OR p_proof.session_expires_at<=current_seconds
       OR (p_proof.state IN ('prepared','claimed') AND p_proof.expires_at<=current_seconds)
       OR (p_proof.state IN ('granted','confirmed') AND
            (p_proof.grant_expires_at<=current_seconds OR p_proof.checked_at<current_seconds-120
             OR p_proof.checked_at>current_seconds+5)) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
END $$;

-- Global order: actor(user/membership) -> RP slot -> account/connection ->
-- proof -> key. The RP slot also serializes 006's counter and revoke operations.
CREATE FUNCTION platform.passkey_action_locked(p_proof uuid,p_rp text,p_binding bytea,
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
    IF NOT FOUND OR item.auth_epoch<>actor.auth_epoch OR item.oidc_issuer<>actor.oidc_issuer
       OR item.oidc_subject<>actor.oidc_subject OR item.oidc_auth_time<>p_oidc_auth_time THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    PERFORM platform.passkey_slot(actor.tenant_id,actor.user_id,p_rp);
    -- Registration has no connection row to lock. Its existing account row
    -- is the durable slot: 003/004 registration writers first take its SHARE
    -- lock, so UPDATE here excludes an insertion through the missing-row gap.
    IF item.target->>'action'='register' THEN
        PERFORM 1 FROM platform.accounts a WHERE a.tenant_id=actor.tenant_id
            AND a.id=item.platform_account_id FOR UPDATE OF a;
        IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    END IF;
    metadata_now:=platform.passkey_action_metadata(item.platform_account_id);
    SELECT r.* INTO STRICT item FROM platform.passkey_action_proofs r WHERE r.proof_id=p_proof FOR UPDATE OF r;
    IF metadata_now IS DISTINCT FROM item.metadata THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF item.target->>'action'='register' AND EXISTS(
        SELECT 1 FROM platform.credential_connections c WHERE c.tenant_id=item.tenant_id
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

CREATE FUNCTION platform.passkey_action_prepare(p_account uuid,p_action text,p_new_connection uuid,
    p_rp text,p_challenge bytea,p_session_binding bytea,p_confirmation_hash bytea,
    p_session_expires bigint,p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_action_attempt_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; metadata_now jsonb; target_now jsonb; key_row record;
    issued_clock bigint; item platform.passkey_action_proofs%ROWTYPE;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    PERFORM platform.passkey_rp(p_rp);
    IF p_account IS NULL OR p_action IS NULL OR p_action NOT IN ('register','replace','revoke')
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
    metadata_now:=platform.passkey_action_metadata(p_account);
    IF p_action='register' THEN
        IF metadata_now->'connection'<>'null'::jsonb OR metadata_now->'account'->>'status'='paused' THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
        -- Never reuse any connection UUID already reserved in this tenant.
        IF EXISTS(SELECT 1 FROM platform.credential_connections c
            WHERE c.tenant_id=actor.tenant_id AND c.connection_id=p_new_connection) THEN
            RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
        END IF;
        target_now:=jsonb_build_object('action',p_action,'platform_account_id',p_account,
            'connection_id',p_new_connection);
    ELSE
        IF metadata_now->'connection'='null'::jsonb
           OR metadata_now->'connection'->>'status'<>'active'
           OR (metadata_now->'connection'->>'credential_revision')::bigint>9007199254740991
           OR (metadata_now->'connection'->>'storage_version')::bigint>=9007199254740991
           OR (p_action='replace' AND (metadata_now->'account'->>'status'='paused'
               OR (metadata_now->'connection'->>'credential_revision')::bigint>=9007199254740991)) THEN
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

CREATE FUNCTION platform.passkey_action_claim(p_proof uuid,p_rp text,p_binding bytea,
    p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_action_attempt_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE item platform.passkey_action_proofs%ROWTYPE; claim_clock bigint;
BEGIN
    item:=platform.passkey_action_locked(p_proof,p_rp,p_binding,p_epoch,p_oidc_auth_time);
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

CREATE FUNCTION platform.passkey_action_finish(p_proof uuid,p_rp text,p_binding bytea,
    p_new_counter bigint,p_backup_eligible boolean,p_backed_up boolean,p_checked_at bigint,
    p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_action_grant_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE item platform.passkey_action_proofs%ROWTYPE; key_row record; grant_clock bigint;
BEGIN
    item:=platform.passkey_action_locked(p_proof,p_rp,p_binding,p_epoch,p_oidc_auth_time);
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

CREATE FUNCTION platform.passkey_action_read_grant(p_grant uuid,p_rp text,p_binding bytea,
    p_epoch bigint,p_oidc_auth_time bigint)
RETURNS SETOF platform.passkey_action_grant_receipt
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; proof uuid; item platform.passkey_action_proofs%ROWTYPE;
BEGIN
    SELECT * INTO STRICT actor FROM platform.passkey_actor(p_epoch,p_oidc_auth_time);
    SELECT r.proof_id INTO proof FROM platform.passkey_action_proofs r WHERE r.grant_id=p_grant
        AND r.tenant_id=actor.tenant_id AND r.user_id=actor.user_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    item:=platform.passkey_action_locked(proof,p_rp,p_binding,p_epoch,p_oidc_auth_time);
    IF item.state<>'granted' THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    PERFORM platform.passkey_action_clock(item);
    RETURN QUERY SELECT * FROM platform.passkey_action_grant_view(item);
END $$;

CREATE FUNCTION platform.passkey_action_confirm(p_grant uuid,p_rp text,p_binding bytea,
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
    item:=platform.passkey_action_locked(proof,p_rp,p_binding,p_epoch,p_oidc_auth_time);
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

REVOKE ALL ON FUNCTION platform.guard_passkey_action_proof(),
    platform.passkey_action_metadata(uuid),
    platform.passkey_action_attempt_view(platform.passkey_action_proofs),
    platform.passkey_action_grant_view(platform.passkey_action_proofs),
    platform.passkey_action_clock(platform.passkey_action_proofs),
    platform.passkey_action_locked(uuid,text,bytea,bigint,bigint),
    platform.passkey_action_prepare(uuid,text,uuid,text,bytea,bytea,bytea,bigint,bigint,bigint),
    platform.passkey_action_claim(uuid,text,bytea,bigint,bigint),
    platform.passkey_action_finish(uuid,text,bytea,bigint,boolean,boolean,bigint,bigint,bigint),
    platform.passkey_action_read_grant(uuid,text,bytea,bigint,bigint),
    platform.passkey_action_confirm(uuid,text,bytea,bytea,bigint,bigint)
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION
    platform.passkey_action_prepare(uuid,text,uuid,text,bytea,bytea,bytea,bigint,bigint,bigint),
    platform.passkey_action_claim(uuid,text,bytea,bigint,bigint),
    platform.passkey_action_finish(uuid,text,bytea,bigint,boolean,boolean,bigint,bigint,bigint),
    platform.passkey_action_read_grant(uuid,text,bytea,bigint,bigint),
    platform.passkey_action_confirm(uuid,text,bytea,bytea,bigint,bigint)
    TO investalo_runtime;
