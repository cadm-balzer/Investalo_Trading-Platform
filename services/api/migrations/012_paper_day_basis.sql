-- Additive Paper-only day input, labeled model provenance.001–011 unchanged.
-- Python owns valuation/RSI/order semantics; SQL trusts the bound Paper writer.
CREATE INDEX paper_journal_day_lookup ON platform.paper_journal(tenant_id,account_id,revision DESC)
  WHERE entry->>'input_kind'='day';

CREATE OR REPLACE FUNCTION platform.paper_payload(p_payload text,p_checksum text,p_revision bigint,
                                        p_tenant uuid,p_account uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d jsonb; c jsonb; e jsonb; proof jsonb; basket jsonb;
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
           OR NOT COALESCE(e->>'input_kind','') IN ('quote','bar','day')
           OR NOT COALESCE(e->>'input_digest','') ~ '^[a-f0-9]{64}$'
           OR jsonb_typeof(e->'fills') IS DISTINCT FROM 'array'
           OR jsonb_typeof(e->'events') IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'Paper journal rejected' USING ERRCODE='22023';
        END IF;
    END IF;
    IF e->>'input_kind'='day' AND (
       e->'fills' IS DISTINCT FROM '[]'::jsonb
       OR jsonb_array_length(e->'events')<>1
       OR e#>>'{events,0,kind}' IS DISTINCT FROM 'daily_baseline_model'
       OR e#>>'{events,0,symbol}' IS DISTINCT FROM ''
       OR e#>>'{events,0,reference}' IS DISTINCT FROM c#>>'{state,account,trading_day}'
       OR (e#>>'{events,0,reason}')::jsonb->>'policy' IS DISTINCT FROM 'paper-h4-close/1'
    ) THEN
      RAISE EXCEPTION 'Paper day evidence rejected' USING ERRCODE='22023';
    END IF;
    -- Day evidence remains authoritative even if a restart precedes bar processing.
    -- Do not accept a changed RSI boundary candle after its model price was frozen.
    SELECT (j.entry#>>'{events,0,reason}')::jsonb INTO proof
      FROM platform.paper_journal j
      WHERE j.tenant_id=p_tenant AND j.account_id=p_account
        AND j.entry->>'input_kind'='day'
        AND j.entry#>>'{events,0,reference}'=c#>>'{state,account,trading_day}'
      ORDER BY j.revision DESC LIMIT 1;
    IF proof IS NOT NULL THEN
      FOR basket IN SELECT value FROM jsonb_array_elements(c#>'{state,baskets}') LOOP
        IF (basket->>'last_bar_open')::timestamptz=
           ((c#>>'{state,account,trading_day}')::date::timestamp AT TIME ZONE 'UTC')-interval '4 hours'
           AND basket->>'last_bar_digest' IS DISTINCT FROM proof#>>ARRAY['bar_digests',basket->>'symbol'] THEN
          RAISE EXCEPTION 'Paper frozen day candle revised' USING ERRCODE='22023';
        END IF;
      END LOOP;
    END IF;
    RETURN c;
END $$;

-- Read-only own-tenant projection for the authenticated API. No writer grants.
-- SQL trusts the API assertion check and its transaction-local identity GUCs.
CREATE OR REPLACE FUNCTION platform.paper_status_rows(p_epoch bigint,p_auth_time timestamptz)
RETURNS TABLE(account_id uuid,account_name text,account_status text,
              snapshot jsonb,journal jsonb)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE t uuid; u uuid;
BEGIN
    IF SESSION_USER<>'investalo_runtime'
       OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname=SESSION_USER
          AND r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolbypassrls
          AND NOT r.rolcreaterole AND NOT r.rolcreatedb AND NOT r.rolreplication) THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    BEGIN
        t:=NULLIF(current_setting('app.tenant_id',true),'')::uuid;
        u:=NULLIF(current_setting('app.user_id',true),'')::uuid;
    EXCEPTION WHEN invalid_text_representation THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END;
    IF t IS NULL OR u IS NULL OR p_epoch IS NULL OR p_auth_time IS NULL THEN
        RAISE EXCEPTION 'access_denied' USING ERRCODE='42501';
    END IF;
    PERFORM 1 FROM platform.users usr JOIN platform.memberships m ON m.user_id=usr.id
      WHERE usr.id=u AND usr.active AND usr.auth_epoch=p_epoch
        AND usr.reauth_after<=p_auth_time
        AND usr.oidc_issuer=current_setting('app.oidc_issuer',true)
        AND usr.oidc_subject=current_setting('app.oidc_subject',true)
        AND m.tenant_id=t AND m.active FOR SHARE OF usr,m;
    IF NOT FOUND THEN RAISE EXCEPTION 'access_denied' USING ERRCODE='42501'; END IF;
    RETURN QUERY
    SELECT a.id,a.name,a.status,
      CASE WHEN c.revision IS NULL THEN NULL ELSE jsonb_build_object(
        'revision',c.revision,'observed_at',c.observed_at,
        'checksum_valid',encode(sha256(convert_to(c.checkpoint,'UTF8')),'hex')=c.checksum,
        'account',(c.checkpoint::jsonb)#>'{checkpoint,state,account}',
        'day_basis_model',EXISTS(SELECT FROM platform.paper_journal dj
          WHERE dj.tenant_id=t AND dj.account_id=a.id AND dj.entry->>'input_kind'='day'
            AND dj.entry#>>'{events,0,kind}'='daily_baseline_model'
            AND dj.entry#>>'{events,0,reference}'=(c.checkpoint::jsonb)#>>'{checkpoint,state,account,trading_day}'),
        'quotes',(c.checkpoint::jsonb)#>'{checkpoint,state,quotes}',
        'positions',(
          SELECT jsonb_agg(jsonb_build_object(
            'symbol',b->'symbol','quantity',b->'quantity',
            'entries',b->'entries','protected',b->'protected',
            'risk_stopped',b->'risk_stopped','stop_price',b->'stop_price',
            'last_bar_open',b->'last_bar_open'))
          FROM jsonb_array_elements((c.checkpoint::jsonb)#>'{checkpoint,state,baskets}') b),
        'open_orders',(
          SELECT count(*) FROM jsonb_array_elements(
            (c.checkpoint::jsonb)#>'{checkpoint,state,orders}') o
          WHERE o->>'status' IN ('open','unknown','cancel_requested'))
      ) END,
      COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
          'revision',j.revision,'at',j.entry->'at','input_kind',j.entry->'input_kind',
          'events',j.entry->'events','fill_count',jsonb_array_length(j.entry->'fills'))
          ORDER BY j.revision DESC)
        FROM (SELECT pj.revision,pj.entry FROM platform.paper_journal pj
          WHERE pj.tenant_id=t AND pj.account_id=a.id
          ORDER BY pj.revision DESC LIMIT 20) j
      ),'[]'::jsonb)
    FROM platform.accounts a LEFT JOIN platform.paper_checkpoints c
      ON c.tenant_id=a.tenant_id AND c.account_id=a.id
    WHERE a.tenant_id=t AND a.broker='bitget' AND a.mode='paper' AND a.currency='USDT'
    ORDER BY a.created_at,a.id LIMIT 20;
END $$;
REVOKE ALL ON FUNCTION platform.paper_status_rows(bigint,timestamptz)
  FROM PUBLIC,investalo_runtime,investalo_research_worker,
       investalo_credentials_worker,investalo_paper_worker;
GRANT EXECUTE ON FUNCTION platform.paper_status_rows(bigint,timestamptz) TO investalo_runtime;
