# KDB-M01-06 Local Owner Return

TO: GPT_BUILDER_KDB
FROM: KDB_CURSOR_LOCAL_SECURITY / KDB-M01-06-CURSOR-LOCAL-SECURITY-HARDENING-001
DATE: 2026-10-23

## 1. STATUS

KDB_M01_06_CURSOR_LOCAL_SECURITY_COMPLETE / PASS_OWNER_QS_SOURCE_ONLY

Uncommitted local P06 source draft on branch `kdb/m01-03-repository-materialization`.
HEAD unchanged: `0aeec974aed9312e74836949471a5fb9f72d2962`
Parent unchanged: `d2a236bfd83e041bff8d785ef763d2c0f5079beb`
origin/main reference: `dd0b145e5f429ff3f8f36f79c2709646d77982a3`

No commit, push, merge, rebase, reset, stash, or SQL apply.

## 2. GATE

STOP_AFTER_LOCAL_UNCOMMITTED_DRAFT / NO_COMMIT_NO_APPLY_NO_PUSH_NO_MERGE

## 3. PLAN_POSITION

KDB-M01 5/10 COMPLETE P04_P05 CONSUMED / P06_LOCAL_DRAFT / P07-P10_NOT_STARTED

## 4. NEXT_EXECUTOR

GPT_BUILDER_KDB / P06_RETURN_CONSUMPTION

## 5. NEXT_PROMPT_URL

Local N06: `docs/kdb/m01/KDB_M01_06_LOCAL_OWNER_RETURN.md` in wordualReality/souvereign-os-coaching-platform
Canonical source: https://docs.google.com/document/d/1IyD4X7Z7Jnh76ANuhKKBVInmwFhkrUWJajxPVK-5YVA/edit
Drive persist of this return: see footer after the one allowed write attempt.

## 6. USER_ACTION

Send one P06 Owner Return. No P04/P05 repeat. No DB/apply/push/merge. P06-LOCAL-COMMIT needs a later exact grant.

## 7. BLOCKER

BLOCK_DEFAULT_ACL_CREATOR (applying user unproven; no ALTER DEFAULT PRIVILEGES FOR ROLE postgres)
PG17_PARSE_NOT_RUN
PHYSICAL_RLS_GRANT_PIAC_TLS_1PASSWORD_UNVERIFIED
LOCAL_SOURCE_BYTES_NOT_INDEPENDENTLY_VERIFIED
TRACKED_PYC_RELEASE_HYGIENE_OPEN
C2_PHYSICAL OPEN. B03 OPEN. RC1B OPEN. QS02 UNAUTHORIZED.

## Preimage

Branch: kdb/m01-03-repository-materialization
B03 untracked, untouched:
- database/migrations/kdb/003__p_kdb_b03_001__legacy_rpc_surface_hardening.sql
- database/migrations/kdb/20261009183000__p_kdb_b03_001__legacy_rpc_surface_hardening.sql
Tracked bytecode left in place.
Preexisting dirty services/api, apps/web, supabase/.temp, docs/arcava, tools/arcava_evidence.py, AGENTS.md, .cursor/permissions.json preserved.

002 preimage SHA-256: a921f35e6f794c74c56fe67f1d5be828d77b325e5eabf936646386ce95dc12bf (kit MATCH)
003 preimage SHA-256: 872427a944914a19a5964eb4f0aa39e64369e36b9141c7cebf58bc6d63d46f29 (P05 repaired; not kit 308d4685...)

## Draft bytes (after P06, uncommitted)

```
e0192986d700177f48bd9b5c04441dc999ce390db9213f36c637a32345d70702  database/migrations/kdb/20261023140100__kdb_m01_002__security_boundary.sql
dfd0496a0a6c56bda3d98dbf2a8ae164327e19640c8366ffa7f49c7bd978067c  database/migrations/kdb/20261023140200__kdb_m01_003__api_boundary.sql
9840b2cae3eecd2b1fdc212df522fc24d8d430cd68af1213cb0f875311e9f709  docs/kdb/m01/KDB_M01_06_SECURITY_BOUNDARY_FREEZE.md
60f9baebd1bbf170681822d2ec6ea4a7790d817c275187ba0a70169ef82e0bba  tests/kdb/kdb_m01_06_security_static.py
50af6117476ef0f6f7bd62451c9835ce97476f41f5afcc60f4ead7f5bd89c4d8  tests/kdb/kdb_m01_06_catalog_oracles.sql
aec2e3ccdb29a3c1b75412827131bf6830229d7f1856ffbd319fbbf9875aa121  tests/kdb/KDB_M01_06_NEGATIVE_TEST_MATRIX.md
6c640e095ebd0b3f1a08c3f4ca187c3cb925a51c8d61c350add3392dc5655cb3  services/kdb/security/PIAC_PROOF_SECURITY_CONTRACT.md
```

Diff: A01 +40/-1, A02 +6/-0. Zero deletions of existing paths. Six new files including this return.

## Tests (do not relabel)

- validate:all: PASS
- P05 repaired-repo tests.kdb alignment+PIAC+promotion: 18/18 PASS (re-run as safe static, not a P04/P05 repair)
- NEW P06 N02 `kdb_m01_06_security_static`: 9/9 PASS
- Original kit 32/32: NOT RE-RUN against mutated 002/003
- PG17_PARSE_NOT_RUN (no psql, no pglast, no pg_query)
- N03 catalog SQL: NOT EXECUTED
- Physical T03-T05, T07, T09, T12: NOT_RUN_NOW

## Hardening summary

002: named ENABLE+FORCE RLS on twelve tables; REVOKE schema/table from PUBLIC/anon/authenticated/service_role and runtime table DML; protected-table REVOKE from command owner; BLOCK_DEFAULT_ACL_CREATOR documented. Kept unproven-user ALTER DEFAULT PRIVILEGES IN SCHEMA kdb_ops as insufficient extra deny.

003: signatures unchanged; named REVOKE EXECUTE on three functions from PUBLIC/anon/authenticated/service_role; comment that tenant_scope GUC is not PIAC.

Facade remains fail-closed. No JWKS, token, or secret.

## Threat notes

1. Default ACLs of other creator roles, including postgres PUBLIC EXECUTE, are unproven until an isolated catalog read names the applying role.
2. `kdb.tenant_scope` can be spoofed by a compromised LOGIN. PIAC must stay fail-closed.
