-- A04-R1: DISPOSABLE ONLY. NOT hosted admission or authenticated identity.
-- Apply before any function creation by the two owner roles. Transaction is
-- supplied by the guarded local harness; a real postcommit restore is unproven.
DO $guard$
DECLARE role_name text;
BEGIN
 IF current_database() <> 'kdb_a04_disposable'
    OR current_setting('server_version_num')::integer / 10000 <> 17
    OR to_regclass('pg_temp.kdb_a04_disposable_guard') IS NULL
    OR session_user <> 'postgres' OR current_user <> 'postgres' THEN
   RAISE EXCEPTION 'BLOCKED_CREATOR_AUTHORITY';
 END IF;
 FOREACH role_name IN ARRAY ARRAY['kdb_schema_owner','kdb_command_owner','kdb_ingest_runtime','kdb_migrator'] LOOP
   IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=role_name AND NOT rolcanlogin
      AND NOT rolinherit AND NOT rolbypassrls AND NOT rolsuper AND NOT rolcreaterole AND NOT rolcreatedb) THEN
      RAISE EXCEPTION 'BLOCKED_CREATOR_AUTHORITY';
   END IF;
 END LOOP;
 -- Complete undirected connected component, not merely grants of protected
 -- roles. The only permitted edges are the three existing synthetic preimage
 -- grants to postgres; their grantor and every PG17 option are pinned.
 IF (SELECT count(*) FROM pg_roles WHERE rolname IN
   ('postgres','kdb_schema_owner','kdb_command_owner','kdb_ingest_runtime','kdb_migrator')) <> 5 THEN
   RAISE EXCEPTION 'BLOCKED_CREATOR_AUTHORITY';
 END IF;
 IF EXISTS (
   WITH RECURSIVE component(oid) AS (
     SELECT oid FROM pg_roles WHERE rolname IN
       ('postgres','kdb_schema_owner','kdb_command_owner','kdb_ingest_runtime','kdb_migrator')
     UNION
     SELECT adjacent.oid FROM component c
       JOIN pg_auth_members m ON m.roleid=c.oid OR m.member=c.oid
       CROSS JOIN LATERAL (VALUES (m.roleid),(m.member)) adjacent(oid)
   )
   SELECT 1 FROM pg_auth_members m JOIN component c ON c.oid=m.roleid
   WHERE NOT (pg_get_userbyid(m.roleid) IN ('kdb_runtime','kdb_ingest_writer','kdb_reviewer')
     AND pg_get_userbyid(m.member)='postgres' AND pg_get_userbyid(m.grantor)='postgres'
     AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option)
 ) OR (SELECT count(*) FROM pg_auth_members m WHERE
     pg_get_userbyid(m.roleid) IN ('kdb_runtime','kdb_ingest_writer','kdb_reviewer')
     AND pg_get_userbyid(m.member)='postgres' AND pg_get_userbyid(m.grantor)='postgres'
     AND m.admin_option AND NOT m.inherit_option AND NOT m.set_option) <> 3 THEN
   RAISE EXCEPTION 'BLOCKED_CREATOR_AUTHORITY';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace n WHERE n.nspname IN
    ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
    AND pg_get_userbyid(n.nspowner) <> 'kdb_schema_owner') THEN
   RAISE EXCEPTION 'BLOCKED_CREATOR_AUTHORITY';
 END IF;
 IF (SELECT count(*) FROM pg_namespace WHERE nspname IN
    ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')) <> 4
 OR EXISTS (
   SELECT 1 FROM pg_namespace n CROSS JOIN pg_roles r
   WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
     AND r.rolname NOT IN ('postgres','kdb_schema_owner')
     AND has_schema_privilege(r.oid,n.oid,'CREATE')
 )
 OR EXISTS (
   SELECT 1 FROM pg_namespace n
   WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
     AND has_schema_privilege('public',n.oid,'CREATE')
 )
 OR EXISTS (
   SELECT 1 FROM pg_namespace n
   CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
   WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
     AND (a.grantee <> n.nspowner OR a.grantor <> n.nspowner OR a.is_grantable)
 ) THEN RAISE EXCEPTION 'BLOCKED_CREATOR_AUTHORITY'; END IF;
 IF (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')) <> 1
 OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
       AND (n.nspname <> 'kdb_ops' OR p.proname <> 'a04_canonical_digest_v2'
         OR p.oid <> to_regprocedure('kdb_ops.a04_canonical_digest_v2(jsonb)')
         OR pg_get_userbyid(p.proowner) <> 'kdb_command_owner'
         OR p.proacl IS NULL OR p.proacl::text <> '{kdb_command_owner=X/kdb_command_owner}'
         OR has_function_privilege('public',p.oid,'EXECUTE')))
 THEN RAISE EXCEPTION 'BLOCKED_CREATOR_AUTHORITY'; END IF;
END $guard$;
ALTER DEFAULT PRIVILEGES FOR ROLE kdb_schema_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE kdb_command_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
DO $verify$
DECLARE role_name text;
BEGIN
 FOREACH role_name IN ARRAY ARRAY['postgres','kdb_schema_owner','kdb_command_owner'] LOOP
   IF NOT EXISTS (
     SELECT 1 FROM pg_default_acl d JOIN pg_roles r ON r.oid=d.defaclrole
     WHERE r.rolname=role_name AND d.defaclnamespace=0 AND d.defaclobjtype='f'
       AND NOT EXISTS (SELECT 1 FROM aclexplode(d.defaclacl) a
         WHERE a.grantee <> r.oid OR a.grantor <> r.oid OR a.is_grantable)
   ) THEN RAISE EXCEPTION 'BLOCKED_CREATOR_AUTHORITY'; END IF;
 END LOOP;
 IF EXISTS (
   SELECT 1 FROM pg_default_acl d JOIN pg_roles r ON r.oid=d.defaclrole
   JOIN pg_namespace n ON n.oid=d.defaclnamespace
   CROSS JOIN LATERAL aclexplode(d.defaclacl) a
   WHERE r.rolname IN ('postgres','kdb_schema_owner','kdb_command_owner')
     AND n.nspname IN ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
     AND d.defaclobjtype='f'
     AND (a.grantee=0 OR a.grantee <> r.oid OR a.grantor <> r.oid OR a.is_grantable)
 ) THEN RAISE EXCEPTION 'BLOCKED_CREATOR_AUTHORITY'; END IF;
END $verify$;
