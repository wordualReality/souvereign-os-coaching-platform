-- Read-only verification queries. Run after an authorized KDB-M01 apply.
-- This packet does not run them.

select n.nspname as schema_name
from pg_namespace n
where n.nspname in ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
order by 1;

select n.nspname as schema_name, c.relname, c.relrowsecurity, c.relforcerowsecurity
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname in ('kdb_canonical','kdb_staging','kdb_governance','kdb_ops')
  and c.relkind = 'r'
order by 1,2;

select rolname, rolcanlogin, rolbypassrls, rolsuper, rolcreaterole
from pg_roles
where rolname in ('kdb_schema_owner','kdb_command_owner','kdb_ingest_runtime')
order by 1;
