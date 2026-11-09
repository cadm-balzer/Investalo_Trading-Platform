-- Read-only own-tenant projection for the authenticated API. No writer grants.
-- SQL trusts the API assertion check and its transaction-local identity GUCs.
CREATE FUNCTION platform.paper_status_rows(p_epoch bigint,p_auth_time timestamptz)
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
