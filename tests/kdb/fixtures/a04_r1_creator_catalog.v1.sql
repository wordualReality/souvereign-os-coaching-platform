-- Read-only disposable catalog evidence, never provider attestation.
SELECT jsonb_build_object(
 'version','kdb.a04-r1.creator-evidence.v1',
 'binding',jsonb_build_object('project_ref','ujdzahwlximlmndexgmx','attestation','SYNTHETIC_ONLY'),
 'source',jsonb_build_object('base_sha','67e417a3ee65ffec2b01da2c3a53e92e7b31c07e',
   'base_manifest_sha256','235c6b9875a068a82db5c9d3c0bae4305d94fa952ad001bd0d5a2fc5eca6d65e',
   'patch_sha256','a6af6706ace9fb1d3b9226bf499db2911d2c80141b87faaacbe1fbb3e12e06e7'),
 'session',jsonb_build_object('session_user',session_user,'current_user',current_user,'identity','SYNTHETIC_SESSION_ONLY_NOT_ATTESTED'),
 'restore',jsonb_build_object('backup','UNVERIFIED','operator','UNVERIFIED'),
 'schemas',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'name',n.nspname,'owner',pg_get_userbyid(n.nspowner),
   'public_create',has_schema_privilege('public',n.oid,'CREATE'),
   'creators',(SELECT coalesce(jsonb_agg(r.rolname ORDER BY r.rolname),'[]'::jsonb) FROM pg_roles r WHERE has_schema_privilege(r.oid,n.oid,'CREATE')),
   'effective_usage',(SELECT jsonb_object_agg(role_name,
      CASE WHEN role_name='PUBLIC' THEN has_schema_privilege('public',n.oid,'USAGE')
        WHEN to_regrole(role_name) IS NULL THEN NULL ELSE has_schema_privilege(role_name,n.oid,'USAGE') END ORDER BY role_name)
     FROM unnest(ARRAY['PUBLIC','anon','authenticated','service_role','kdb_ingest_runtime','kdb_migrator','kdb_schema_owner','kdb_command_owner','postgres']) AS u(role_name)),
   'acl_entries',(SELECT coalesce(jsonb_agg(jsonb_build_object(
     'grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
     'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type),'[]'::jsonb)
     FROM aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a),
   'acl_safe',NOT EXISTS(SELECT 1 FROM aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
     WHERE a.grantor<>n.nspowner OR a.is_grantable OR
       (a.grantee<>n.nspowner AND NOT (n.nspname='kdb_ops' AND a.grantee=to_regrole('kdb_migrator'))))
   ) ORDER BY n.nspname),'[]'::jsonb) FROM pg_namespace n
   WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')),
 'creators',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'role',r.rolname,'login',r.rolcanlogin,'superuser',r.rolsuper,'inherit',r.rolinherit,'bypassrls',r.rolbypassrls,'createrole',r.rolcreaterole,'createdb',r.rolcreatedb,
   'global_default_raw',d.defaclacl::text,'default_namespace','GLOBAL','object_type','f',
   'acl_entries',(SELECT coalesce(jsonb_agg(jsonb_build_object(
     'grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
     'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type),'[]'::jsonb) FROM aclexplode(d.defaclacl) a),
   'default_safe',d.oid IS NOT NULL AND NOT EXISTS(SELECT 1 FROM aclexplode(d.defaclacl) a
     WHERE a.grantee<>r.oid OR a.grantor<>r.oid OR a.is_grantable),
   'scoped_defaults_safe',NOT EXISTS(
     SELECT 1 FROM pg_default_acl sd JOIN pg_namespace sn ON sn.oid=sd.defaclnamespace
     CROSS JOIN LATERAL aclexplode(sd.defaclacl) a
     WHERE sd.defaclrole=r.oid AND sd.defaclobjtype='f'
       AND sn.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
       AND (a.grantee<>r.oid OR a.grantor<>r.oid OR a.is_grantable))
   ) ORDER BY r.rolname),'[]'::jsonb) FROM pg_roles r
   LEFT JOIN pg_default_acl d ON d.defaclrole=r.oid AND d.defaclnamespace=0 AND d.defaclobjtype='f'
   WHERE r.rolname IN ('postgres','kdb_schema_owner','kdb_command_owner','kdb_migrator')),
 'memberships',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'role',pg_get_userbyid(m.roleid),'member',pg_get_userbyid(m.member),'grantor',pg_get_userbyid(m.grantor),
   'admin',m.admin_option,'inherit',m.inherit_option,'set',m.set_option) ORDER BY m.roleid,m.member,m.grantor),'[]'::jsonb)
   FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid
   WHERE r.rolname IN ('kdb_schema_owner','kdb_command_owner','kdb_ingest_runtime','kdb_migrator')),
 'functions',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'schema',n.nspname,'name',p.proname,'signature',p.oid::regprocedure::text,'owner',pg_get_userbyid(p.proowner),
   'definition_sha256',encode(extensions.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex'),
   'raw_acl',p.proacl::text,'public_execute',has_function_privilege('public',p.oid,'EXECUTE'),
   'runtime_execute',has_function_privilege('kdb_ingest_runtime',p.oid,'EXECUTE'),
   'acl_entries',(SELECT coalesce(jsonb_agg(jsonb_build_object(
     'grantor',pg_get_userbyid(a.grantor),'grantee',CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
     'privilege',a.privilege_type,'grantable',a.is_grantable) ORDER BY a.grantor,a.grantee,a.privilege_type),'[]'::jsonb)
     FROM aclexplode(p.proacl) a),
   'acl_safe',p.proacl IS NOT NULL AND NOT EXISTS(SELECT 1 FROM aclexplode(p.proacl) a
     WHERE a.grantor<>p.proowner OR a.is_grantable OR (a.grantee<>p.proowner AND a.grantee<>to_regrole('kdb_migrator')))
   ) ORDER BY n.nspname,p.proname,p.oid::regprocedure::text),'[]'::jsonb)
   FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops'))
)::text;
