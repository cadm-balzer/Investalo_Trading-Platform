-- Run as investalo_migration. An administrator first creates the NOLOGIN
-- investalo_credentials_worker group and independently provisions narrow LOGINs.
-- No keys, role creation, network access or credential decryption in SQL.
CREATE TABLE platform.credential_role_bindings (
    database_role name PRIMARY KEY,
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id)
);
CREATE TABLE platform.credential_connections (
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    platform_account_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    broker_uid text NOT NULL CHECK(broker_uid ~ '^[1-9][0-9]{0,19}$'),
    parent_uid text CHECK(parent_uid='0' OR parent_uid ~ '^[1-9][0-9]{0,19}$'),
    broker text NOT NULL DEFAULT 'bitget' CHECK(broker='bitget'),
    account_family text NOT NULL DEFAULT 'classic_v2' CHECK(account_family='classic_v2'),
    connection_mode text NOT NULL DEFAULT 'real_read_only' CHECK(connection_mode='real_read_only'),
    credential_revision bigint NOT NULL CHECK(credential_revision>0),
    storage_version bigint NOT NULL CHECK(storage_version>0),
    status text NOT NULL CHECK(status IN ('active','revoked')),
    envelope jsonb NOT NULL,
    PRIMARY KEY(tenant_id,connection_id),
    UNIQUE(broker,broker_uid),
    UNIQUE(tenant_id,platform_account_id),
    FOREIGN KEY(tenant_id,user_id) REFERENCES platform.memberships(tenant_id,user_id),
    FOREIGN KEY(tenant_id,platform_account_id) REFERENCES platform.accounts(tenant_id,id)
);

ALTER TABLE platform.credential_role_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.credential_role_bindings FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.credential_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.credential_connections FORCE ROW LEVEL SECURITY;
CREATE POLICY migration_management ON platform.credential_role_bindings
    TO investalo_migration USING(true) WITH CHECK(true);
CREATE POLICY migration_management ON platform.credential_connections
    TO investalo_migration USING(true) WITH CHECK(true);
-- FORCE RLS has only management policies. The worker has no direct table grant;
-- narrowly granted definer functions are its only access path.
REVOKE ALL ON platform.credential_role_bindings,platform.credential_connections
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT USAGE ON SCHEMA platform TO investalo_credentials_worker;

CREATE FUNCTION platform.credential_context()
RETURNS TABLE(tenant_id uuid,user_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    -- SESSION_USER survives SET ROLE and cannot be replaced by request GUCs.
    -- Dynamic role/membership checks also reject post-provision privilege drift.
    IF NOT pg_has_role(SESSION_USER,'investalo_credentials_worker','MEMBER')
       OR NOT EXISTS(SELECT 1 FROM pg_roles r WHERE r.rolname=SESSION_USER
            AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
            AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication)
       OR EXISTS(SELECT 1 FROM pg_roles r
            WHERE r.rolname<>'investalo_credentials_worker' AND r.rolname<>SESSION_USER
              AND pg_has_role(SESSION_USER,r.oid,'MEMBER'))
       OR EXISTS(SELECT 1 FROM pg_auth_members membership
            JOIN pg_roles r ON r.oid=membership.member
            WHERE r.rolname=SESSION_USER AND membership.admin_option) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    RETURN QUERY SELECT b.tenant_id,b.user_id
        FROM platform.credential_role_bindings b
        JOIN platform.users u ON u.id=b.user_id AND u.active
        JOIN platform.memberships m ON m.tenant_id=b.tenant_id AND m.user_id=b.user_id
            AND m.active AND m.role IN ('owner','trader')
        WHERE b.database_role=SESSION_USER
        FOR SHARE OF b,u,m;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
END $$;

CREATE FUNCTION platform.credential_envelope_valid(p_envelope jsonb)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE field text; decoded bytea;
BEGIN
    IF p_envelope IS NULL OR jsonb_typeof(p_envelope)<>'object'
       OR octet_length(p_envelope::text)>8192 THEN RETURN false; END IF;
    IF (SELECT count(*) FROM jsonb_object_keys(p_envelope))<>6
       OR NOT p_envelope ?& ARRAY['schema_version','kek_id','payload_nonce',
                                  'wrap_nonce','wrapped_dek','ciphertext'] THEN RETURN false; END IF;
    FOREACH field IN ARRAY ARRAY['schema_version','kek_id','payload_nonce',
                                 'wrap_nonce','wrapped_dek','ciphertext'] LOOP
        IF jsonb_typeof(p_envelope->field)<>'string' THEN RETURN false; END IF;
    END LOOP;
    IF p_envelope->>'schema_version'<>'credential-envelope/1'
       OR NOT (p_envelope->>'kek_id') ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'
       OR length(p_envelope->>'ciphertext') NOT BETWEEN 24 AND 5484 THEN RETURN false; END IF;
    FOREACH field IN ARRAY ARRAY['payload_nonce','wrap_nonce','wrapped_dek','ciphertext'] LOOP
        IF NOT (p_envelope->>field) ~ '^[A-Za-z0-9+/]+={0,2}$' THEN RETURN false; END IF;
        decoded:=decode(p_envelope->>field,'base64');
        IF replace(encode(decoded,'base64'),E'\n','')<>p_envelope->>field
           OR (field IN ('payload_nonce','wrap_nonce') AND octet_length(decoded)<>12)
           OR (field='wrapped_dek' AND octet_length(decoded)<>48)
           OR (field='ciphertext' AND octet_length(decoded) NOT BETWEEN 17 AND 4112)
           THEN RETURN false; END IF;
    END LOOP;
    RETURN true;
EXCEPTION WHEN OTHERS THEN
    RETURN false;
END $$;
ALTER TABLE platform.credential_connections ADD CONSTRAINT credential_envelope_shape
    CHECK(platform.credential_envelope_valid(envelope));

CREATE FUNCTION platform.guard_credential_connection()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    ELSIF TG_OP='INSERT' THEN
        IF NEW.status<>'active' OR NEW.credential_revision<>1 OR NEW.storage_version<>1 THEN
            RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
        END IF;
    ELSE
        IF OLD.status='revoked'
           OR (OLD.tenant_id,OLD.user_id,OLD.platform_account_id,OLD.connection_id,
               OLD.broker_uid,OLD.parent_uid,OLD.broker,OLD.account_family,OLD.connection_mode)
              IS DISTINCT FROM
              (NEW.tenant_id,NEW.user_id,NEW.platform_account_id,NEW.connection_id,
               NEW.broker_uid,NEW.parent_uid,NEW.broker,NEW.account_family,NEW.connection_mode)
           OR OLD.storage_version=9223372036854775807
           OR NEW.storage_version<>OLD.storage_version+1 THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
        IF NEW.status='revoked' THEN
            IF NEW.credential_revision<>OLD.credential_revision OR NEW.envelope IS DISTINCT FROM OLD.envelope THEN
                RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
            END IF;
        ELSIF NEW.status<>'active' OR
              (NEW.credential_revision<>OLD.credential_revision AND
               (OLD.credential_revision=9223372036854775807 OR NEW.credential_revision<>OLD.credential_revision+1)) OR
              (NEW.credential_revision=OLD.credential_revision AND
               (NEW.envelope->'payload_nonce' IS DISTINCT FROM OLD.envelope->'payload_nonce'
                OR NEW.envelope->'ciphertext' IS DISTINCT FROM OLD.envelope->'ciphertext')) THEN
            RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER guarded_credential_connection BEFORE INSERT OR UPDATE OR DELETE
    ON platform.credential_connections FOR EACH ROW EXECUTE FUNCTION platform.guard_credential_connection();
CREATE TRIGGER credential_connection_no_truncate BEFORE TRUNCATE
    ON platform.credential_connections FOR EACH STATEMENT EXECUTE FUNCTION platform.guard_credential_connection();

-- Internal helper: never executable by the worker, and no caller-selected owner.
CREATE FUNCTION platform.credential_owned(p_connection uuid,p_for_revoke boolean DEFAULT false)
RETURNS platform.credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE context_row record; connection_row platform.credential_connections%ROWTYPE;
BEGIN
    SELECT * INTO STRICT context_row FROM platform.credential_context();
    SELECT c.* INTO connection_row FROM platform.credential_connections c
        JOIN platform.accounts a ON a.tenant_id=c.tenant_id AND a.id=c.platform_account_id
        WHERE c.tenant_id=context_row.tenant_id AND c.user_id=context_row.user_id
          AND c.connection_id=p_connection AND c.status='active'
          AND (p_for_revoke OR (a.broker='bitget' AND a.mode='read_only' AND a.status<>'paused'))
        FOR UPDATE OF c FOR SHARE OF a;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    RETURN connection_row;
END $$;

CREATE FUNCTION platform.credential_create(p_platform_account uuid,p_connection uuid,
    p_broker_uid text,p_parent_uid text,p_envelope jsonb)
RETURNS SETOF platform.credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE context_row record;
BEGIN
    SELECT * INTO STRICT context_row FROM platform.credential_context();
    PERFORM 1 FROM platform.accounts a
        WHERE a.tenant_id=context_row.tenant_id AND a.id=p_platform_account
          AND a.broker='bitget' AND a.mode='read_only' AND a.status<>'paused'
        FOR SHARE OF a;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    IF p_connection IS NULL OR p_broker_uid IS NULL OR NOT p_broker_uid ~ '^[1-9][0-9]{0,19}$'
       OR (p_parent_uid IS NOT NULL AND NOT (p_parent_uid='0' OR p_parent_uid ~ '^[1-9][0-9]{0,19}$'))
       OR NOT platform.credential_envelope_valid(p_envelope) THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    RETURN QUERY INSERT INTO platform.credential_connections
        (tenant_id,user_id,platform_account_id,connection_id,broker_uid,parent_uid,
         credential_revision,storage_version,status,envelope)
        VALUES(context_row.tenant_id,context_row.user_id,p_platform_account,p_connection,
               p_broker_uid,p_parent_uid,1,1,'active',p_envelope) RETURNING *;
EXCEPTION WHEN unique_violation THEN
    RAISE EXCEPTION 'identity_conflict' USING ERRCODE='23505';
END $$;

CREATE FUNCTION platform.credential_read(p_connection uuid)
RETURNS SETOF platform.credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    RETURN NEXT platform.credential_owned(p_connection);
END $$;

CREATE FUNCTION platform.credential_replace(p_connection uuid,p_expected_revision bigint,
    p_expected_storage bigint,p_envelope jsonb)
RETURNS SETOF platform.credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE connection_row platform.credential_connections%ROWTYPE;
BEGIN
    connection_row:=platform.credential_owned(p_connection);
    IF p_expected_revision IS DISTINCT FROM connection_row.credential_revision
       OR p_expected_storage IS DISTINCT FROM connection_row.storage_version THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF connection_row.credential_revision=9223372036854775807
       OR connection_row.storage_version=9223372036854775807
       OR NOT platform.credential_envelope_valid(p_envelope) THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    RETURN QUERY UPDATE platform.credential_connections c
        SET credential_revision=c.credential_revision+1,storage_version=c.storage_version+1,envelope=p_envelope
        WHERE c.tenant_id=connection_row.tenant_id AND c.connection_id=connection_row.connection_id
        RETURNING c.*;
END $$;

CREATE FUNCTION platform.credential_rewrap(p_connection uuid,p_expected_revision bigint,
    p_expected_storage bigint,p_envelope jsonb)
RETURNS SETOF platform.credential_connections
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE connection_row platform.credential_connections%ROWTYPE;
BEGIN
    connection_row:=platform.credential_owned(p_connection);
    IF p_expected_revision IS DISTINCT FROM connection_row.credential_revision
       OR p_expected_storage IS DISTINCT FROM connection_row.storage_version THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF connection_row.storage_version=9223372036854775807
       OR NOT platform.credential_envelope_valid(p_envelope)
       OR p_envelope->'payload_nonce' IS DISTINCT FROM connection_row.envelope->'payload_nonce'
       OR p_envelope->'ciphertext' IS DISTINCT FROM connection_row.envelope->'ciphertext' THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    RETURN QUERY UPDATE platform.credential_connections c
        SET storage_version=c.storage_version+1,envelope=p_envelope
        WHERE c.tenant_id=connection_row.tenant_id AND c.connection_id=connection_row.connection_id
        RETURNING c.*;
END $$;

CREATE FUNCTION platform.credential_revoke(p_connection uuid,p_expected_revision bigint,p_expected_storage bigint)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE connection_row platform.credential_connections%ROWTYPE; version bigint;
BEGIN
    -- Revocation remains possible even if the account has been paused or its
    -- read gates changed administratively; user/membership ownership is mandatory.
    connection_row:=platform.credential_owned(p_connection,true);
    IF p_expected_revision IS DISTINCT FROM connection_row.credential_revision
       OR p_expected_storage IS DISTINCT FROM connection_row.storage_version THEN
        RAISE EXCEPTION 'concurrent_change' USING ERRCODE='40001';
    END IF;
    IF connection_row.storage_version=9223372036854775807 THEN
        RAISE EXCEPTION 'invalid_record' USING ERRCODE='22023';
    END IF;
    UPDATE platform.credential_connections c SET status='revoked',storage_version=c.storage_version+1
        WHERE c.tenant_id=connection_row.tenant_id AND c.connection_id=connection_row.connection_id
        RETURNING c.storage_version INTO version;
    RETURN version;
END $$;

REVOKE ALL ON FUNCTION platform.credential_context(),platform.credential_envelope_valid(jsonb),
    platform.guard_credential_connection(),platform.credential_owned(uuid,boolean),
    platform.credential_create(uuid,uuid,text,text,jsonb),platform.credential_read(uuid),
    platform.credential_replace(uuid,bigint,bigint,jsonb),platform.credential_rewrap(uuid,bigint,bigint,jsonb),
    platform.credential_revoke(uuid,bigint,bigint)
    FROM PUBLIC,investalo_runtime,investalo_research_worker,investalo_credentials_worker;
GRANT EXECUTE ON FUNCTION platform.credential_context(),
    platform.credential_create(uuid,uuid,text,text,jsonb),platform.credential_read(uuid),
    platform.credential_replace(uuid,bigint,bigint,jsonb),platform.credential_rewrap(uuid,bigint,bigint,jsonb),
    platform.credential_revoke(uuid,bigint,bigint) TO investalo_credentials_worker;
