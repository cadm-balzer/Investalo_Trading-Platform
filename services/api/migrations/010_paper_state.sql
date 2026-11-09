-- Administrator provisions investalo_paper_worker NOLOGIN before migration.
-- Functions trust the bound Python worker for strategy/economic calculations.
CREATE TABLE platform.paper_role_bindings (
    database_role name PRIMARY KEY,
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    active boolean NOT NULL DEFAULT true,
    UNIQUE(tenant_id,account_id),
    FOREIGN KEY(tenant_id,account_id) REFERENCES platform.accounts(tenant_id,id)
);
CREATE TABLE platform.paper_checkpoints (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision>=0),
    checkpoint text NOT NULL CHECK(octet_length(checkpoint) BETWEEN 1 AND 16777216),
    checksum text NOT NULL CHECK(checksum ~ '^[a-f0-9]{64}$'),
    configuration_digest text NOT NULL,
    cost_digest text NOT NULL,
    observed_at timestamptz NOT NULL,
    PRIMARY KEY(tenant_id,account_id),
    FOREIGN KEY(tenant_id,account_id) REFERENCES platform.accounts(tenant_id,id)
);
CREATE TABLE platform.paper_journal (
    tenant_id uuid NOT NULL,
    account_id uuid NOT NULL,
    revision bigint NOT NULL CHECK(revision>0),
    previous_checksum text NOT NULL,
    checkpoint_checksum text NOT NULL,
    entry jsonb NOT NULL CHECK(jsonb_typeof(entry)='object'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(tenant_id,account_id,revision),
    FOREIGN KEY(tenant_id,account_id) REFERENCES platform.paper_checkpoints(tenant_id,account_id)
);
DO $$
DECLARE item text;
BEGIN
    FOREACH item IN ARRAY ARRAY['paper_role_bindings','paper_checkpoints','paper_journal']
    LOOP
        EXECUTE format('ALTER TABLE platform.%I ENABLE ROW LEVEL SECURITY',item);
        EXECUTE format('ALTER TABLE platform.%I FORCE ROW LEVEL SECURITY',item);
        EXECUTE format('CREATE POLICY migration_management ON platform.%I
            TO investalo_migration USING(true) WITH CHECK(true)',item);
    END LOOP;
END $$;

CREATE FUNCTION platform.paper_journal_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'Paper journal is immutable' USING ERRCODE='42501';
END $$;
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON platform.paper_journal
FOR EACH ROW EXECUTE FUNCTION platform.paper_journal_immutable();
CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON platform.paper_journal
FOR EACH STATEMENT EXECUTE FUNCTION platform.paper_journal_immutable();

CREATE FUNCTION platform.paper_actor() RETURNS TABLE(tenant uuid,account uuid,account_status text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    RETURN QUERY SELECT b.tenant_id,b.account_id,a.status
    FROM platform.paper_role_bindings b
    JOIN platform.accounts a ON (a.tenant_id,a.id)=(b.tenant_id,b.account_id)
    JOIN pg_catalog.pg_roles r ON r.rolname=SESSION_USER
    WHERE b.database_role=SESSION_USER AND b.active
      AND a.mode='paper' AND a.broker='bitget' AND a.currency='USDT'
      AND a.status IN ('ready','paused')
      AND r.rolcanlogin AND NOT (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole
                                OR r.rolcreatedb OR r.rolreplication)
    -- Serialize initialization/writes and exclude concurrent account pause/rebind.
    FOR UPDATE OF b,a;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Paper actor rejected' USING ERRCODE='42501';
    END IF;
END $$;

CREATE FUNCTION platform.paper_payload(p_payload text,p_checksum text,p_revision bigint,
                                        p_tenant uuid,p_account uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d jsonb; c jsonb; e jsonb;
BEGIN
    IF p_payload IS NULL OR p_checksum IS NULL OR p_revision IS NULL
       OR octet_length(p_payload) NOT BETWEEN 1 AND 16777216
       OR p_checksum !~ '^[a-f0-9]{64}$'
       OR encode(sha256(convert_to(p_payload,'UTF8')),'hex')<>p_checksum THEN
        RAISE EXCEPTION 'Paper payload rejected' USING ERRCODE='22023';
    END IF;
    d:=p_payload::jsonb;
    c:=d->'checkpoint';
    IF jsonb_typeof(d) IS DISTINCT FROM 'object'
       OR d->>'schema_version' IS DISTINCT FROM 'paper-checkpoint/1'
       OR d->>'mode' IS DISTINCT FROM 'paper'
       OR d-ARRAY['schema_version','mode','checkpoint']<>'{}'::jsonb
       OR jsonb_typeof(c) IS DISTINCT FROM 'object'
       OR c-ARRAY['state','cost_digest','revision','observed_at','last_entry']<>'{}'::jsonb
       OR jsonb_typeof(c->'revision') IS DISTINCT FROM 'number'
       OR c->>'revision' IS DISTINCT FROM p_revision::text
       OR c#>>'{state,version}' IS DISTINCT FROM 'crypto-basket/1.0.0'
       OR c#>>'{state,account,tenant_id}' IS DISTINCT FROM p_tenant::text
       OR c#>>'{state,account,account_id}' IS DISTINCT FROM p_account::text
       OR c#>>'{state,account,initial_equity}' IS DISTINCT FROM '10000'
       OR NOT COALESCE(c#>>'{state,configuration_digest}','') ~ '^[a-f0-9]{64}$'
       OR NOT COALESCE(c->>'cost_digest','') ~ '^[a-f0-9]{64}$'
       OR jsonb_typeof(c->'observed_at') IS DISTINCT FROM 'string' THEN
        RAISE EXCEPTION 'Paper binding rejected' USING ERRCODE='22023';
    END IF;
    PERFORM (c->>'observed_at')::timestamptz;
    e:=c->'last_entry';
    IF p_revision=0 THEN
        IF e IS DISTINCT FROM 'null'::jsonb
           OR c#>>'{state,account,cash}' IS DISTINCT FROM '10000'
           OR c#>>'{state,account,day_start_equity}' IS DISTINCT FROM '10000'
           OR c#>'{state,orders}' IS DISTINCT FROM '[]'::jsonb
           OR c#>'{state,quotes}' IS DISTINCT FROM '[]'::jsonb
           OR c#>'{state,processed_fills}' IS DISTINCT FROM '[]'::jsonb
           OR c#>'{state,processed_bars}' IS DISTINCT FROM '[]'::jsonb
           OR c#>'{state,closed_baskets}' IS DISTINCT FROM '[]'::jsonb THEN
            RAISE EXCEPTION 'Paper initial state rejected' USING ERRCODE='22023';
        END IF;
    ELSE
        IF jsonb_typeof(e) IS DISTINCT FROM 'object'
           OR e-ARRAY['revision','at','input_kind','input_digest','fills','events']<>'{}'::jsonb
           OR jsonb_typeof(e->'revision') IS DISTINCT FROM 'number'
           OR e->>'revision' IS DISTINCT FROM p_revision::text
           OR e->>'at' IS DISTINCT FROM c->>'observed_at'
           OR NOT COALESCE(e->>'input_kind','') IN ('quote','bar')
           OR NOT COALESCE(e->>'input_digest','') ~ '^[a-f0-9]{64}$'
           OR jsonb_typeof(e->'fills') IS DISTINCT FROM 'array'
           OR jsonb_typeof(e->'events') IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'Paper journal rejected' USING ERRCODE='22023';
        END IF;
    END IF;
    RETURN c;
END $$;

CREATE FUNCTION platform.paper_read() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; result jsonb;
BEGIN
    SELECT * INTO STRICT actor FROM platform.paper_actor();
    SELECT jsonb_build_object('checkpoint',s.checkpoint,'checksum',s.checksum,'revision',s.revision)
    INTO result FROM platform.paper_checkpoints s
    WHERE (s.tenant_id,s.account_id)=(actor.tenant,actor.account);
    RETURN result;
END $$;

CREATE FUNCTION platform.paper_initialize(p_payload text,p_checksum text) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; c jsonb; old platform.paper_checkpoints;
BEGIN
    SELECT * INTO STRICT actor FROM platform.paper_actor();
    IF actor.account_status<>'ready' THEN
        RAISE EXCEPTION 'Paper account paused' USING ERRCODE='42501';
    END IF;
    c:=platform.paper_payload(p_payload,p_checksum,0,actor.tenant,actor.account);
    SELECT * INTO old FROM platform.paper_checkpoints
    WHERE (tenant_id,account_id)=(actor.tenant,actor.account) FOR UPDATE;
    IF FOUND THEN
        IF old.revision=0 AND old.checksum=p_checksum THEN RETURN 0; END IF;
        RAISE EXCEPTION 'Paper state conflict' USING ERRCODE='40001';
    END IF;
    INSERT INTO platform.paper_checkpoints VALUES(
        actor.tenant,actor.account,0,p_payload,p_checksum,
        c#>>'{state,configuration_digest}',c->>'cost_digest',(c->>'observed_at')::timestamptz);
    RETURN 0;
END $$;

CREATE FUNCTION platform.paper_commit(p_expected bigint,p_previous_checksum text,
                                      p_payload text,p_checksum text) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor record; c jsonb; old platform.paper_checkpoints;
BEGIN
    SELECT * INTO STRICT actor FROM platform.paper_actor();
    IF actor.account_status<>'ready' THEN
        RAISE EXCEPTION 'Paper account paused' USING ERRCODE='42501';
    END IF;
    IF p_expected IS NULL OR p_expected<0 OR p_expected>=9223372036854775807
       OR p_previous_checksum IS NULL THEN
        RAISE EXCEPTION 'Paper revision rejected' USING ERRCODE='22023';
    END IF;
    c:=platform.paper_payload(p_payload,p_checksum,p_expected+1,actor.tenant,actor.account);
    SELECT * INTO old FROM platform.paper_checkpoints
    WHERE (tenant_id,account_id)=(actor.tenant,actor.account) FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Paper state conflict' USING ERRCODE='40001';
    END IF;
    -- Exact last committed update can be acknowledged without a second journal row.
    IF old.revision=p_expected+1 AND old.checksum=p_checksum AND EXISTS(
        SELECT FROM platform.paper_journal j
        WHERE (j.tenant_id,j.account_id,j.revision)=(actor.tenant,actor.account,p_expected+1)
        AND j.previous_checksum=p_previous_checksum AND j.checkpoint_checksum=p_checksum
    ) THEN RETURN old.revision; END IF;
    IF old.revision<>p_expected OR old.checksum<>p_previous_checksum
       OR old.configuration_digest IS DISTINCT FROM c#>>'{state,configuration_digest}'
       OR old.cost_digest IS DISTINCT FROM c->>'cost_digest'
       OR (c->>'observed_at')::timestamptz<old.observed_at THEN
        RAISE EXCEPTION 'Paper state conflict' USING ERRCODE='40001';
    END IF;
    INSERT INTO platform.paper_journal(tenant_id,account_id,revision,previous_checksum,
                                       checkpoint_checksum,entry)
    VALUES(actor.tenant,actor.account,p_expected+1,p_previous_checksum,p_checksum,c->'last_entry');
    UPDATE platform.paper_checkpoints SET revision=p_expected+1,checkpoint=p_payload,
        checksum=p_checksum,observed_at=(c->>'observed_at')::timestamptz
    WHERE (tenant_id,account_id)=(actor.tenant,actor.account);
    RETURN p_expected+1;
END $$;

REVOKE ALL ON FUNCTION platform.paper_actor(),
    platform.paper_journal_immutable(),
    platform.paper_payload(text,text,bigint,uuid,uuid),platform.paper_read(),
    platform.paper_initialize(text,text),platform.paper_commit(bigint,text,text,text) FROM PUBLIC;
GRANT USAGE ON SCHEMA platform TO investalo_paper_worker;
GRANT EXECUTE ON FUNCTION platform.paper_read(),platform.paper_initialize(text,text),
    platform.paper_commit(bigint,text,text,text) TO investalo_paper_worker;
-- No direct table rights, GUC-selected actor, runtime/research access or credential rights.
