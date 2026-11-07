-- The administrator creates the NOLOGIN group investalo_research_worker first.
-- No role creation, credentials or network access are part of this migration.
CREATE TABLE platform.research_role_bindings (
    database_role name PRIMARY KEY,
    tenant_id uuid NOT NULL UNIQUE REFERENCES platform.tenants(id)
);
ALTER TABLE platform.research_role_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.research_role_bindings FORCE ROW LEVEL SECURITY;
CREATE POLICY migration_management ON platform.research_role_bindings
    TO investalo_migration USING(true) WITH CHECK(true);

CREATE FUNCTION platform.research_tenant() RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog
AS $$
    SELECT tenant_id FROM platform.research_role_bindings
    WHERE database_role = SESSION_USER
$$;
REVOKE ALL ON FUNCTION platform.research_tenant() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform.research_tenant() TO investalo_research_worker;
GRANT USAGE ON SCHEMA platform TO investalo_research_worker;

CREATE TABLE platform.research_datasets (
    tenant_id uuid NOT NULL REFERENCES platform.tenants(id),
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    purpose text NOT NULL CHECK(purpose IN ('research','test','holdout')),
    symbol text NOT NULL CHECK(symbol IN ('BTC/USDT','ETH/USDT')),
    timeframe text NOT NULL CHECK(timeframe = '4h'),
    source jsonb NOT NULL CHECK(jsonb_typeof(source) = 'object'),
    synthetic boolean NOT NULL,
    bar_count integer NOT NULL CHECK(bar_count BETWEEN 1 AND 10000),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL CHECK(ends_at > starts_at),
    data_digest text NOT NULL CHECK(data_digest ~ '^[a-f0-9]{64}$'),
    content_digest text NOT NULL CHECK(content_digest ~ '^[a-f0-9]{64}$'),
    coverage_complete boolean,
    snapshot jsonb NOT NULL CHECK(jsonb_typeof(snapshot) = 'object'
                                AND octet_length(snapshot::text) <= 8388608),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,id),
    UNIQUE(tenant_id,purpose,symbol,data_digest),
    CHECK(NOT synthetic OR purpose = 'test')
);
ALTER TABLE platform.research_datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.research_datasets FORCE ROW LEVEL SECURITY;
CREATE POLICY migration_management ON platform.research_datasets
    TO investalo_migration USING(true) WITH CHECK(true);
CREATE POLICY runtime_research_data ON platform.research_datasets TO investalo_runtime
    USING(tenant_id = NULLIF(current_setting('app.tenant_id',true),'')::uuid
          AND purpose IN ('research','test'));
CREATE POLICY worker_research_data ON platform.research_datasets TO investalo_research_worker
    USING(tenant_id = platform.research_tenant() AND purpose IN ('research','test'));
GRANT SELECT ON platform.research_datasets TO investalo_runtime, investalo_research_worker;
GRANT SELECT ON platform.jobs TO investalo_research_worker;
ALTER TABLE platform.jobs
    ADD COLUMN dataset_id uuid,
    ADD COLUMN strategy_version text,
    ADD COLUMN configuration_digest text,
    ADD COLUMN cost_digest text,
    ADD COLUMN frozen_specification jsonb,
    ADD COLUMN attempt_token uuid,
    ADD COLUMN attempt_count integer NOT NULL DEFAULT 0 CHECK(attempt_count BETWEEN 0 AND 3),
    ADD COLUMN completed_at timestamptz,
    ADD COLUMN failure_code text,
    ADD COLUMN result_summary jsonb,
    ADD CONSTRAINT job_dataset FOREIGN KEY(tenant_id,dataset_id)
        REFERENCES platform.research_datasets(tenant_id,id),
    ADD CONSTRAINT known_research_failure CHECK(failure_code IS NULL OR failure_code IN
        ('dataset_missing','snapshot_invalid','configuration_mismatch',
         'simulation_failed','attempts_exhausted')),
    ADD CONSTRAINT configuration_digest_format CHECK(configuration_digest IS NULL
        OR configuration_digest ~ '^[a-f0-9]{64}$'),
    ADD CONSTRAINT cost_digest_format CHECK(cost_digest IS NULL
        OR cost_digest ~ '^[a-f0-9]{64}$');
CREATE POLICY worker_jobs ON platform.jobs TO investalo_research_worker
    USING(tenant_id = platform.research_tenant()
          AND EXISTS(SELECT 1 FROM platform.research_datasets s
                     WHERE s.tenant_id = jobs.tenant_id AND s.id = jobs.dataset_id
                     AND s.purpose IN ('research','test')));
-- Earlier queued records had no frozen input. Never silently attach later data.
UPDATE platform.jobs SET status='failed', failure_code='dataset_missing',
    completed_at=clock_timestamp(), lease_until=NULL
    WHERE dataset_id IS NULL;
ALTER TABLE platform.jobs ADD CONSTRAINT frozen_research_input CHECK(
    status='failed' OR
    (dataset_id IS NOT NULL AND strategy_version IS NOT NULL
     AND configuration_digest IS NOT NULL AND cost_digest IS NOT NULL
     AND frozen_specification IS NOT NULL));
ALTER TABLE platform.jobs ADD CONSTRAINT successful_research_output CHECK(
    (status='succeeded' AND result IS NOT NULL AND result_summary IS NOT NULL
     AND completed_at IS NOT NULL AND failure_code IS NULL)
    OR (status<>'succeeded' AND result IS NULL AND result_summary IS NULL));
ALTER TABLE platform.jobs ADD CONSTRAINT bounded_research_lease CHECK(
    (status='running' AND lease_until IS NOT NULL AND attempt_token IS NOT NULL AND attempt_count>0)
    OR (status<>'running' AND lease_until IS NULL AND attempt_token IS NULL));
ALTER TABLE platform.jobs ADD CONSTRAINT failed_research_reason CHECK(
    status<>'failed' OR (failure_code IS NOT NULL AND completed_at IS NOT NULL));

CREATE FUNCTION platform.reject_dataset_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'Research snapshots are immutable' USING ERRCODE='42501';
END $$;
REVOKE ALL ON FUNCTION platform.reject_dataset_mutation() FROM PUBLIC;
CREATE TRIGGER immutable_research_dataset BEFORE UPDATE OR DELETE
    ON platform.research_datasets FOR EACH ROW EXECUTE FUNCTION platform.reject_dataset_mutation();
CREATE TRIGGER immutable_research_dataset_truncate BEFORE TRUNCATE
    ON platform.research_datasets FOR EACH STATEMENT EXECUTE FUNCTION platform.reject_dataset_mutation();

CREATE FUNCTION platform.guard_research_job() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE data_row record;
BEGIN
    IF TG_OP='INSERT' AND NEW.status<>'queued' THEN
        RAISE EXCEPTION 'Research jobs must enter the queue' USING ERRCODE='42501';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (OLD.tenant_id,OLD.id,OLD.created_by,OLD.kind,OLD.payload,OLD.payload_hash,
            OLD.idempotency_key,OLD.created_at,OLD.dataset_id,OLD.strategy_version,
            OLD.configuration_digest,OLD.cost_digest,OLD.frozen_specification)
           IS DISTINCT FROM
           (NEW.tenant_id,NEW.id,NEW.created_by,NEW.kind,NEW.payload,NEW.payload_hash,
            NEW.idempotency_key,NEW.created_at,NEW.dataset_id,NEW.strategy_version,
            NEW.configuration_digest,NEW.cost_digest,NEW.frozen_specification) THEN
            RAISE EXCEPTION 'Frozen job inputs cannot change' USING ERRCODE='42501';
        END IF;
        IF OLD.status IN ('succeeded','failed','cancelled') AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Terminal research jobs are immutable' USING ERRCODE='42501';
        END IF;
    END IF;
    IF NEW.dataset_id IS NOT NULL THEN
        SELECT purpose,symbol,data_digest INTO data_row
        FROM platform.research_datasets
        WHERE tenant_id=NEW.tenant_id AND id=NEW.dataset_id;
        IF NOT FOUND OR data_row.purpose='holdout'
           OR NEW.payload->>'symbol' IS DISTINCT FROM data_row.symbol
           OR NEW.payload->>'data_digest' IS DISTINCT FROM data_row.data_digest
           OR NEW.payload->>'dataset_id' IS DISTINCT FROM NEW.dataset_id::text THEN
            RAISE EXCEPTION 'Research dataset unavailable' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION platform.guard_research_job() FROM PUBLIC;
CREATE TRIGGER frozen_research_job BEFORE INSERT OR UPDATE
    ON platform.jobs FOR EACH ROW EXECUTE FUNCTION platform.guard_research_job();

CREATE FUNCTION platform.research_claim(p_lease_seconds integer DEFAULT 120)
RETURNS TABLE(job_id uuid, tenant_id uuid, attempt_token uuid, attempt_number integer,
              payload jsonb, dataset_id uuid, strategy_version text,
              configuration_digest text, cost_digest text, frozen_specification jsonb,
              lease_until timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE bound_tenant uuid := platform.research_tenant();
BEGIN
    IF bound_tenant IS NULL OR p_lease_seconds IS NULL OR p_lease_seconds NOT BETWEEN 5 AND 300 THEN
        RAISE EXCEPTION 'Research identity unavailable' USING ERRCODE='42501';
    END IF;
    WITH exhausted AS (
        SELECT j.id FROM platform.jobs j
        WHERE j.tenant_id=bound_tenant AND j.status='running'
          AND j.lease_until<=clock_timestamp() AND j.attempt_count>=3
        ORDER BY j.created_at,j.id LIMIT 100 FOR UPDATE SKIP LOCKED
    )
    UPDATE platform.jobs j SET status='failed',failure_code='attempts_exhausted',
        completed_at=clock_timestamp(),lease_until=NULL,attempt_token=NULL
    FROM exhausted WHERE j.tenant_id=bound_tenant AND j.id=exhausted.id;
    RETURN QUERY
    WITH selected AS (
        SELECT j.id FROM platform.jobs j
        JOIN platform.research_datasets s ON s.tenant_id=j.tenant_id AND s.id=j.dataset_id
        WHERE j.tenant_id=bound_tenant AND j.kind='backtest'
          AND s.purpose IN ('research','test') AND j.attempt_count<3
          AND (j.status='queued' OR (j.status='running' AND j.lease_until<=clock_timestamp()))
        ORDER BY j.created_at,j.id LIMIT 1 FOR UPDATE OF j SKIP LOCKED
    )
    UPDATE platform.jobs j SET status='running',attempt_count=j.attempt_count+1,
        attempt_token=gen_random_uuid(),
        lease_until=clock_timestamp()+make_interval(secs=>p_lease_seconds)
    FROM selected WHERE j.tenant_id=bound_tenant AND j.id=selected.id
    RETURNING j.id,j.tenant_id,j.attempt_token,j.attempt_count,j.payload,j.dataset_id,
              j.strategy_version,j.configuration_digest,j.cost_digest,j.frozen_specification,j.lease_until;
END $$;

CREATE FUNCTION platform.research_heartbeat(p_job uuid,p_token uuid,p_lease_seconds integer DEFAULT 120)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE affected integer;
BEGIN
    IF p_lease_seconds IS NULL OR p_lease_seconds NOT BETWEEN 5 AND 300
       OR platform.research_tenant() IS NULL THEN
        RAISE EXCEPTION 'Research identity unavailable' USING ERRCODE='42501';
    END IF;
    UPDATE platform.jobs j
    SET lease_until=clock_timestamp()+make_interval(secs=>p_lease_seconds)
    WHERE j.tenant_id=platform.research_tenant() AND j.id=p_job
      AND j.attempt_token=p_token AND j.status='running' AND j.lease_until>clock_timestamp();
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected=1;
END $$;

CREATE FUNCTION platform.research_complete(p_job uuid,p_token uuid,p_result jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE job_row platform.jobs%ROWTYPE; data_row platform.research_datasets%ROWTYPE;
        key_name text; number_value text; curve_point jsonb; previous_at timestamptz;
BEGIN
    IF platform.research_tenant() IS NULL THEN
        RAISE EXCEPTION 'Research identity unavailable' USING ERRCODE='42501';
    END IF;
    SELECT * INTO job_row FROM platform.jobs j
    WHERE j.tenant_id=platform.research_tenant() AND j.id=p_job FOR UPDATE;
    IF NOT FOUND OR job_row.status<>'running' OR job_row.attempt_token IS DISTINCT FROM p_token
       OR job_row.lease_until<=clock_timestamp() THEN
        RETURN false;
    END IF;
    SELECT * INTO data_row FROM platform.research_datasets
    WHERE tenant_id=job_row.tenant_id AND id=job_row.dataset_id AND purpose IN ('research','test');
    IF NOT FOUND OR jsonb_typeof(p_result) IS DISTINCT FROM 'object'
       OR octet_length(p_result::text)>2097152
       OR p_result->>'schema_version' IS DISTINCT FROM 'backtest-result/1'
       OR p_result->>'symbol' IS DISTINCT FROM data_row.symbol
       OR p_result->>'timeframe' IS DISTINCT FROM '4h'
       OR p_result->>'strategy_version' IS DISTINCT FROM job_row.strategy_version
       OR p_result->>'configuration_digest' IS DISTINCT FROM job_row.configuration_digest
       OR p_result->>'cost_digest' IS DISTINCT FROM job_row.cost_digest
       OR p_result->>'data_digest' IS DISTINCT FROM data_row.data_digest
       OR jsonb_typeof(p_result->'simulation_data_digest') IS DISTINCT FROM 'string'
       OR NOT COALESCE(p_result->>'simulation_data_digest','') ~ '^[a-f0-9]{64}$'
       OR p_result->'source' IS DISTINCT FROM
          (CASE WHEN data_row.source->>'venue'='bitget' THEN data_row.source
                ELSE jsonb_set(data_row.source,'{url}','null'::jsonb) END)
       OR p_result->'coverage' IS DISTINCT FROM data_row.snapshot->'coverage'
       OR p_result->'cost_assumptions' IS DISTINCT FROM jsonb_build_object(
          'fee_rate',job_row.frozen_specification->'costs'->'fee_rate',
          'spread_fraction',job_row.frozen_specification->'costs'->'spread_fraction',
          'slippage_fraction',job_row.frozen_specification->'costs'->'slippage_fraction',
          'initial_equity',job_row.frozen_specification->'configuration'->'initial_equity',
          'basket_principal',job_row.frozen_specification->'configuration'->'basket_principal',
          'basket_cost_reserve',job_row.frozen_specification->'configuration'->'basket_cost_reserve')
       OR p_result->'synthetic' IS DISTINCT FROM to_jsonb(data_row.synthetic)
       OR p_result->'bar_count' IS DISTINCT FROM to_jsonb(data_row.bar_count)
       OR p_result->'validation'->>'status' IS DISTINCT FROM 'not_evaluated'
       OR jsonb_typeof(p_result->'equity_curve') IS DISTINCT FROM 'array'
       OR jsonb_array_length(p_result->'equity_curve') NOT BETWEEN 1 AND 2000 THEN
        RAISE EXCEPTION 'Research result rejected' USING ERRCODE='22023';
    END IF;
    IF (p_result->>'start')::timestamptz IS DISTINCT FROM data_row.starts_at
       OR (p_result->>'end')::timestamptz IS DISTINCT FROM data_row.ends_at
       OR NOT p_result ?& ARRAY[
          'schema_version','symbol','timeframe','strategy_version','data_digest','simulation_data_digest',
          'configuration_digest','cost_digest','source','synthetic','bar_count','start','end','net_pnl',
          'maximum_drawdown_fraction','profit_factor','closed_basket_count','equity_curve',
          'equity_curve_sampled','cost_assumptions','coverage','validation']
       OR p_result-ARRAY[
          'schema_version','symbol','timeframe','strategy_version','data_digest','simulation_data_digest',
          'configuration_digest','cost_digest','source','synthetic','bar_count','start','end','net_pnl',
          'maximum_drawdown_fraction','profit_factor','closed_basket_count','equity_curve',
          'equity_curve_sampled','cost_assumptions','coverage','validation'] <> '{}'::jsonb THEN
        RAISE EXCEPTION 'Research result rejected' USING ERRCODE='22023';
    END IF;
    FOREACH key_name IN ARRAY ARRAY['net_pnl','maximum_drawdown_fraction','profit_factor'] LOOP
        IF key_name='profit_factor' AND p_result->key_name='null'::jsonb THEN CONTINUE; END IF;
        number_value := p_result->>key_name;
        IF jsonb_typeof(p_result->key_name) IS DISTINCT FROM 'string'
           OR length(number_value)>64 OR NOT COALESCE(number_value,'') ~ '^-?[0-9]+(\.[0-9]+)?$' THEN
            RAISE EXCEPTION 'Research numeric result rejected' USING ERRCODE='22023';
        END IF;
        IF abs(number_value::numeric)>1000000000000
           OR (key_name<>'net_pnl' AND number_value::numeric<0)
           OR (key_name='maximum_drawdown_fraction' AND number_value::numeric>1) THEN
            RAISE EXCEPTION 'Research numeric result rejected' USING ERRCODE='22023';
        END IF;
    END LOOP;
    FOR curve_point IN SELECT value FROM jsonb_array_elements(p_result->'equity_curve') LOOP
        number_value := curve_point->>'equity';
        IF jsonb_typeof(curve_point) IS DISTINCT FROM 'object'
           OR NOT curve_point ?& ARRAY['at','equity']
           OR curve_point-ARRAY['at','equity']<>'{}'::jsonb
           OR jsonb_typeof(curve_point->'at') IS DISTINCT FROM 'string'
           OR length(curve_point->>'at')>40
           OR jsonb_typeof(curve_point->'equity') IS DISTINCT FROM 'string'
           OR length(number_value)>64 OR NOT COALESCE(number_value,'') ~ '^[0-9]+(\.[0-9]+)?$' THEN
            RAISE EXCEPTION 'Research curve rejected' USING ERRCODE='22023';
        END IF;
        IF number_value::numeric>1000000000000
           OR (curve_point->>'at')::timestamptz NOT BETWEEN data_row.starts_at AND data_row.ends_at
           OR (previous_at IS NOT NULL AND (curve_point->>'at')::timestamptz<previous_at) THEN
            RAISE EXCEPTION 'Research curve rejected' USING ERRCODE='22023';
        END IF;
        previous_at := (curve_point->>'at')::timestamptz;
    END LOOP;
    UPDATE platform.jobs SET status='succeeded',result=p_result,
        result_summary=p_result-'equity_curve',completed_at=clock_timestamp(),
        lease_until=NULL,attempt_token=NULL,failure_code=NULL
    WHERE tenant_id=job_row.tenant_id AND id=job_row.id;
    RETURN true;
END $$;

CREATE FUNCTION platform.research_fail(p_job uuid,p_token uuid,p_code text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE affected integer;
BEGIN
    IF platform.research_tenant() IS NULL
       OR p_code IS NULL
       OR p_code NOT IN ('snapshot_invalid','configuration_mismatch','simulation_failed') THEN
        RAISE EXCEPTION 'Research failure rejected' USING ERRCODE='22023';
    END IF;
    UPDATE platform.jobs j SET status='failed',failure_code=p_code,
        completed_at=clock_timestamp(),lease_until=NULL,attempt_token=NULL
    WHERE j.tenant_id=platform.research_tenant() AND j.id=p_job
      AND j.attempt_token=p_token AND j.status='running' AND j.lease_until>clock_timestamp();
    GET DIAGNOSTICS affected=ROW_COUNT;
    RETURN affected=1;
END $$;
REVOKE ALL ON FUNCTION platform.research_claim(integer),
    platform.research_heartbeat(uuid,uuid,integer),
    platform.research_complete(uuid,uuid,jsonb),
    platform.research_fail(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION platform.research_claim(integer),
    platform.research_heartbeat(uuid,uuid,integer),
    platform.research_complete(uuid,uuid,jsonb),
    platform.research_fail(uuid,uuid,text) TO investalo_research_worker;
-- Workers have no table writes, DDL, runtime membership access or broker secrets.
