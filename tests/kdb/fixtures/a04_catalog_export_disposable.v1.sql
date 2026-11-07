-- Read-only synthetic exporter; inputs are local fixture tables, not hosted.
-- Claimed target is explicitly synthetic and is never provider attestation.
SELECT jsonb_build_object(
 'version','kdb.a04.catalog-export.disposable.v1',
 'binding',jsonb_build_object('claimed_project_ref','ujdzahwlximlmndexgmx',
   'export_origin','SYNTHETIC_LOCAL_FIXTURE','attestation','SYNTHETIC_ONLY'),
 'ledger',(SELECT coalesce(jsonb_agg(to_jsonb(l) ORDER BY version),'[]'::jsonb)
   FROM synthetic_migration_registry.ledger l),
 'protocol_count',(SELECT count(*) FROM canonical.protocol),
 'protocol_provenance','UNKNOWN',
 'schemas',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'name',n.nspname,'owner',pg_get_userbyid(n.nspowner),'raw_acl',n.nspacl::text,
   'effective_usage',jsonb_build_object(
     'PUBLIC',has_schema_privilege('public',n.oid,'USAGE'),
     'anon',CASE WHEN to_regrole('anon') IS NULL THEN NULL ELSE has_schema_privilege('anon',n.oid,'USAGE') END,
     'authenticated',CASE WHEN to_regrole('authenticated') IS NULL THEN NULL ELSE has_schema_privilege('authenticated',n.oid,'USAGE') END,
     'service_role',CASE WHEN to_regrole('service_role') IS NULL THEN NULL ELSE has_schema_privilege('service_role',n.oid,'USAGE') END,
     'kdb_ingest_runtime',CASE WHEN to_regrole('kdb_ingest_runtime') IS NULL THEN NULL ELSE has_schema_privilege('kdb_ingest_runtime',n.oid,'USAGE') END),
   'acl',coalesce((SELECT jsonb_agg(jsonb_build_object(
     'grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
     'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type)
     FROM aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a),'[]'::jsonb)
   ) ORDER BY n.nspname),'[]'::jsonb) FROM pg_namespace n
   WHERE n.nspname IN ('canonical','dev_staging','kdb_api','kdb_audit','kdb_canonical','kdb_staging','kdb_governance','kdb_ops')),
 'relations',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'schema',n.nspname,'name',c.relname,'kind',c.relkind::text,'owner',pg_get_userbyid(c.relowner),
   'rls',c.relrowsecurity,'force_rls',c.relforcerowsecurity,'raw_acl',c.relacl::text,
   'acl',coalesce((SELECT jsonb_agg(jsonb_build_object(
     'grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
     'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type)
     FROM aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a),'[]'::jsonb)
   ) ORDER BY n.nspname,c.relname,c.relkind),'[]'::jsonb) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname IN ('canonical','dev_staging','kdb_api','kdb_audit','kdb_canonical','kdb_staging','kdb_governance','kdb_ops') AND c.relkind IN ('r','p','v','m','f','S')),
 'policies',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'schema',n.nspname,'table',c.relname,'name',p.polname,'command',p.polcmd::text,
   'roles',to_jsonb(p.polroles),'using',pg_get_expr(p.polqual,p.polrelid),
   'with_check',pg_get_expr(p.polwithcheck,p.polrelid)) ORDER BY n.nspname,c.relname,p.polname),'[]'::jsonb)
   FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname IN ('canonical','dev_staging','kdb_api','kdb_audit','kdb_canonical','kdb_staging','kdb_governance','kdb_ops')),
 'roles',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'name',r.rolname,'login',r.rolcanlogin,'inherit',r.rolinherit,'bypassrls',r.rolbypassrls,
   'superuser',r.rolsuper,'createrole',r.rolcreaterole,'createdb',r.rolcreatedb) ORDER BY r.rolname),'[]'::jsonb)
   FROM pg_roles r WHERE r.rolname LIKE 'kdb\_%' ESCAPE '\'),
 'memberships',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'role',pg_get_userbyid(m.roleid),'member',pg_get_userbyid(m.member),'grantor',pg_get_userbyid(m.grantor),
   'admin',m.admin_option,'inherit',m.inherit_option,'set',m.set_option) ORDER BY m.roleid,m.member,m.grantor),'[]'::jsonb)
   FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid WHERE r.rolname LIKE 'kdb\_%' ESCAPE '\'),
 'default_function_acl',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'creator',pg_get_userbyid(d.defaclrole),'schema',coalesce(n.nspname,'GLOBAL'),'raw_acl',d.defaclacl::text,
   'acl',coalesce((SELECT jsonb_agg(jsonb_build_object(
     'grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
     'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type)
     FROM aclexplode(d.defaclacl) a),'[]'::jsonb)) ORDER BY d.defaclrole,d.defaclnamespace),'[]'::jsonb)
   FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
   WHERE d.defaclobjtype='f' AND (d.defaclnamespace=0 OR n.nspname IN ('canonical','dev_staging','kdb_api','kdb_audit','kdb_canonical','kdb_staging','kdb_governance','kdb_ops'))),
 'functions',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'schema',n.nspname,'signature',p.oid::regprocedure::text,'owner',pg_get_userbyid(p.proowner),
   'security_definer',p.prosecdef,'search_path',p.proconfig,'raw_acl',p.proacl::text,
   'acl',coalesce((SELECT jsonb_agg(jsonb_build_object(
     'grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
     'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type)
     FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a),'[]'::jsonb),
   'effective_visibility',jsonb_build_object(
     'PUBLIC',has_schema_privilege('public',n.oid,'USAGE') AND has_function_privilege('public',p.oid,'EXECUTE'),
     'anon',CASE WHEN to_regrole('anon') IS NULL THEN NULL ELSE has_schema_privilege('anon',n.oid,'USAGE') AND has_function_privilege('anon',p.oid,'EXECUTE') END,
     'authenticated',CASE WHEN to_regrole('authenticated') IS NULL THEN NULL ELSE has_schema_privilege('authenticated',n.oid,'USAGE') AND has_function_privilege('authenticated',p.oid,'EXECUTE') END,
     'service_role',CASE WHEN to_regrole('service_role') IS NULL THEN NULL ELSE has_schema_privilege('service_role',n.oid,'USAGE') AND has_function_privilege('service_role',p.oid,'EXECUTE') END,
     'kdb_ingest_runtime',CASE WHEN to_regrole('kdb_ingest_runtime') IS NULL THEN NULL ELSE has_schema_privilege('kdb_ingest_runtime',n.oid,'USAGE') AND has_function_privilege('kdb_ingest_runtime',p.oid,'EXECUTE') END)
   ) ORDER BY n.nspname,p.oid::regprocedure::text),'[]'::jsonb)
   FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname IN ('canonical','dev_staging','kdb_api','kdb_audit','kdb_canonical','kdb_staging','kdb_governance','kdb_ops')),
 'pgcrypto',(SELECT jsonb_build_object('extension',e.extname,'namespace',n.nspname,
   'digest_signature',to_regprocedure('extensions.digest(bytea,text)')::text,
   'digest_raw_acl',(SELECT proacl::text FROM pg_proc WHERE oid=to_regprocedure('extensions.digest(bytea,text)')),
   'digest_public_execute',CASE WHEN to_regprocedure('extensions.digest(bytea,text)') IS NULL THEN NULL ELSE has_function_privilege('public','extensions.digest(bytea,text)','EXECUTE') END)
   FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='pgcrypto'),
 'admission','NOT_AUTHORIZED'
)::text;
