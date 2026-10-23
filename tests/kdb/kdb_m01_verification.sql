-- Read-only verification queries. Run after KDB-M01 apply.

select n.nspname as schema_name, c.relname, c.relrowsecurity, c.relforcerowsecurity
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname in ('canonical','dev_staging','kdb_audit')
  and c.relkind = 'r'
order by 1,2;

select rolname, rolcanlogin, rolbypassrls, rolsuper, rolcreaterole
from pg_roles
where rolname in ('kdb_runtime','kdb_ingest_writer','kdb_reviewer')
order by 1;

select routine_schema, routine_name, security_type
from information_schema.routines
where routine_schema in ('kdb_api','kdb_audit')
order by 1,2;

select grantee, routine_schema, routine_name, privilege_type
from information_schema.role_routine_grants
where routine_schema = 'kdb_api'
order by 1,2,3;

select schemaname, tablename, policyname, roles, cmd
from pg_policies
where schemaname in ('canonical','dev_staging','kdb_audit')
order by 1,2,3;

select version, name
from supabase_migrations.schema_migrations
order by version;
