-- Terminal evidence for the private passkey onboarding executor.
-- 008's immutable consent/consume/lock records are unchanged. A completed
-- terminal row and the matching 003 mutation must commit in the same transaction.
-- SQL trusts the private verifier, Classic probe and AEAD implementation. Direct
-- 003 storage functions remain trusted primitives, not a universal MFA boundary.
CREATE TABLE platform.passkey_credential_completion_audit (
    authorization_id uuid PRIMARY KEY REFERENCES platform.passkey_credential_authorizations(authorization_id),
    outcome text NOT NULL CHECK(outcome IN ('completed','failed')),
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    platform_account_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    action text NOT NULL CHECK(action IN ('register','replace','revoke')),
    credential_revision bigint,
    storage_version bigint,
    connection_status text,
    database_role name NOT NULL DEFAULT SESSION_USER,
    transaction_id xid8 NOT NULL DEFAULT pg_current_xact_id(),
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id),
    FOREIGN KEY(tenant_id,platform_account_id) REFERENCES platform.accounts(tenant_id,id),
    CHECK((outcome='failed' AND credential_revision IS NULL AND storage_version IS NULL AND connection_status IS NULL)
       OR (outcome='completed' AND credential_revision IS NOT NULL AND storage_version IS NOT NULL
           AND connection_status IS NOT NULL AND credential_revision BETWEEN 1 AND 9007199254740991
           AND storage_version BETWEEN 1 AND 9007199254740991
           AND connection_status=(CASE WHEN action='revoke' THEN 'revoked' ELSE 'active' END)))
);
ALTER TABLE platform.passkey_credential_completion_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.passkey_credential_completion_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY migration_management ON platform.passkey_credential_completion_audit
    TO investalo_migration USING(true) WITH CHECK(true);
REVOKE ALL ON platform.passkey_credential_completion_audit
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
CREATE TRIGGER immutable_passkey_credential_completion_audit BEFORE UPDATE OR DELETE
    ON platform.passkey_credential_completion_audit FOR EACH ROW
    EXECUTE FUNCTION platform.reject_credential_audit_mutation();
CREATE TRIGGER passkey_credential_completion_audit_no_truncate BEFORE TRUNCATE
    ON platform.passkey_credential_completion_audit FOR EACH STATEMENT
    EXECUTE FUNCTION platform.reject_credential_audit_mutation();

-- 008's locked helper compares the OLD metadata and cannot validate a completed
-- mutation. This separate helper compares only the permitted NEW connection
-- state; all frozen actor, account, factor and receipt bindings remain exact.
-- Order: actor -> RP slot -> account/connection -> proof -> key -> authorization.
CREATE FUNCTION platform.credential_passkey_completion_locked(p_claims jsonb,p_outcome text)
RETURNS platform.passkey_credential_authorizations
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; user_row record; key_row record;
    proof platform.passkey_action_proofs%ROWTYPE;
    purpose platform.passkey_credential_authorizations%ROWTYPE;
    metadata_now jsonb; expected_metadata jsonb;
    final_revision bigint; final_storage bigint; final_status text;
BEGIN
    IF p_outcome IS NULL OR p_outcome NOT IN ('completed','failed')
       OR NOT platform.passkey_credential_claims_valid(p_claims) THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    SELECT * INTO STRICT actor FROM platform.credential_context();
    IF actor.tenant_id::text<>p_claims->>'tenant_id' OR actor.user_id::text<>p_claims->>'user_id' THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    SELECT x.* INTO STRICT user_row FROM platform.users x WHERE x.id=actor.user_id;
    IF p_outcome='completed' AND
       (user_row.auth_epoch<>(p_claims->>'auth_epoch')::bigint
        OR user_row.oidc_issuer<>p_claims->>'oidc_iss' OR user_row.oidc_subject<>p_claims->>'sub'
        OR extract(epoch FROM user_row.reauth_after)>(p_claims->>'oidc_auth_time')::bigint) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    SELECT a.* INTO purpose FROM platform.passkey_credential_authorizations a
        WHERE a.authorization_id=(p_claims->>'authorization_id')::uuid;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    SELECT r.* INTO proof FROM platform.passkey_action_proofs r WHERE r.proof_id=purpose.proof_id
        AND r.tenant_id=actor.tenant_id AND r.user_id=actor.user_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    PERFORM platform.passkey_slot(actor.tenant_id,actor.user_id,proof.rp_id);
    IF p_outcome='completed' THEN
        metadata_now:=platform.credential_passkey_metadata(actor.tenant_id,actor.user_id,user_row.auth_epoch,
            proof.platform_account_id,proof.target->>'action');
    END IF;
    SELECT r.* INTO STRICT proof FROM platform.passkey_action_proofs r
        WHERE r.proof_id=purpose.proof_id FOR UPDATE OF r;
    IF p_outcome='completed' THEN
        SELECT x.* INTO key_row FROM platform.passkey_credentials x WHERE x.passkey_id=proof.passkey_id
            AND x.tenant_id=actor.tenant_id AND x.user_id=actor.user_id AND x.rp_id=proof.rp_id FOR SHARE OF x;
        IF NOT FOUND OR key_row.status<>'active' OR key_row.enrollment_epoch<>user_row.auth_epoch
           OR key_row.oidc_issuer<>user_row.oidc_issuer OR key_row.oidc_subject<>user_row.oidc_subject THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
        IF key_row.storage_version IS DISTINCT FROM proof.passkey_version THEN
            RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
        END IF;
    END IF;
    SELECT a.* INTO STRICT purpose FROM platform.passkey_credential_authorizations a
        WHERE a.authorization_id=(p_claims->>'authorization_id')::uuid FOR UPDATE OF a;
    IF proof.state<>'confirmed' OR purpose.consumed_by IS DISTINCT FROM SESSION_USER
       OR purpose.consume_transaction IS NULL OR purpose.consume_transaction=pg_current_xact_id()
       OR purpose.consumed_claims IS DISTINCT FROM p_claims
       OR purpose.receipt IS DISTINCT FROM platform.passkey_credential_receipt(purpose,proof)
       OR purpose.receipt IS DISTINCT FROM platform.passkey_credential_claims_receipt(p_claims)
       OR EXISTS(SELECT 1 FROM platform.passkey_credential_completion_audit a
            WHERE a.authorization_id=purpose.authorization_id) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    IF p_outcome='completed' THEN
        IF purpose.state<>'locked' OR purpose.lock_transaction IS DISTINCT FROM pg_current_xact_id() THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
        IF proof.target->>'action'='register' THEN
            final_revision:=1; final_storage:=1; final_status:='active';
        ELSE
            final_revision:=(proof.target->>'expected_revision')::bigint;
            final_storage:=(proof.target->>'expected_storage')::bigint+1;
            IF proof.target->>'action'='replace' THEN
                final_revision:=final_revision+1; final_status:='active';
            ELSE
                final_status:='revoked';
            END IF;
        END IF;
        expected_metadata:=jsonb_set(proof.metadata,'{connection}',jsonb_build_object(
            'connection_id',proof.target->>'connection_id','credential_revision',final_revision,
            'storage_version',final_storage,'status',final_status));
        IF metadata_now IS DISTINCT FROM expected_metadata THEN
            RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
        END IF;
        PERFORM platform.passkey_credential_claims_clock(p_claims);
    ELSE
        -- Harmless failure evidence is possible after an expired/revoked proof,
        -- but only after the final lock/write transaction rolled back. It grants
        -- no write and cannot mislabel or overwrite a committed completion.
        IF purpose.state<>'consumed' THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    END IF;
    RETURN purpose;
END $$;

CREATE FUNCTION platform.credential_finish_passkey_authorization(p_claims jsonb,p_outcome text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE purpose platform.passkey_credential_authorizations%ROWTYPE; target jsonb;
    final_revision bigint; final_storage bigint; final_status text;
BEGIN
    purpose:=platform.credential_passkey_completion_locked(p_claims,p_outcome);
    target:=purpose.receipt->'target';
    IF p_outcome='completed' THEN
        IF target->>'action'='register' THEN
            final_revision:=1; final_storage:=1; final_status:='active';
        ELSE
            final_revision:=(target->>'expected_revision')::bigint;
            final_storage:=(target->>'expected_storage')::bigint+1;
            IF target->>'action'='replace' THEN
                final_revision:=final_revision+1; final_status:='active';
            ELSE
                final_status:='revoked';
            END IF;
        END IF;
        PERFORM platform.passkey_credential_claims_clock(p_claims);
    END IF;
    INSERT INTO platform.passkey_credential_completion_audit
        (authorization_id,outcome,tenant_id,user_id,platform_account_id,connection_id,action,
         credential_revision,storage_version,connection_status)
        VALUES(purpose.authorization_id,p_outcome,(purpose.receipt->>'tenant_id')::uuid,
            (purpose.receipt->>'user_id')::uuid,(target->>'platform_account_id')::uuid,
            (target->>'connection_id')::uuid,target->>'action',final_revision,final_storage,final_status);
    IF p_outcome='completed' THEN
        -- Audit/FK/table locks can wait after the mutation. Expiry aborts the
        -- entire final transaction, including 003's write and 008's lock marker.
        PERFORM platform.passkey_credential_claims_clock(p_claims);
    END IF;
    RETURN true;
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
END $$;
REVOKE ALL ON FUNCTION platform.credential_passkey_completion_locked(jsonb,text),
    platform.credential_finish_passkey_authorization(jsonb,text)
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION platform.credential_finish_passkey_authorization(jsonb,text)
    TO investalo_credentials_worker;
-- Terminal tombstones remain retained. A failed audit does not change 008's
-- consumed marker; a later trusted final writer must require successful finish.
