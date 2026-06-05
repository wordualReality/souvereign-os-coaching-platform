## `python scripts/validate_repo.py`

Return code: `0`

```text
PASS repo required-file check count=15

```

## `python scripts/validate_openapi.py`

Return code: `0`

```text
PASS OpenAPI structural check: contracts/openapi/project-b-v1.json paths=51
PASS OpenAPI structural check: contracts/openapi/project-b-v1.1-overlay.json paths=10
PASS OpenAPI structural check: contracts/openapi/project-b-v1.yaml paths=51
PASS OpenAPI overlay hardening endpoint check

```

## `python scripts/validate_json_schemas.py`

Return code: `0`

```text
PASS JSON/schema parse + schema-check count=48

```

## `python scripts/validate_sql_static.py`

Return code: `0`

```text
PASS SQL static migration check: database/migrations/001_project_b_baseline_schema.sql create_table_count=73
PASS SQL static migration check: database/migrations/002_project_b_journey_provisioning_hardening.sql create_table_count=11
NOTE: true SQL dry-run requires Postgres/Supabase CLI; this static check is the sandbox fallback.

```

## `python scripts/validate_rls_static.py`

Return code: `0`

```text
PASS RLS static check: policies=145

```

## `python scripts/validate_mvp_slice_01.py`

Return code: `0`

```text
PASS MVP Slice 01 skeleton coverage

```
