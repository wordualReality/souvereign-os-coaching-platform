# P25 creator-specific default ACL local hardening

Packet: `KDB-M01-P25-PG17-CREATOR-DEFAULT-ACL-LOCAL-HARDENING-01`

Status: `LOCAL_PG17_CREATOR_PROOF / NON_APPLY_CANDIDATE / NOT_SECURITY_PASS`

The accepted migrations 001–003 remain unchanged. The bounded SQL candidate
lives only at `tests/kdb/fixtures/p25_creator_default_acl_candidate.sql` and is
never auto-applied. It requires a direct login where `session_user` and
`current_user` both equal the proven creator.

## Correct default-ACL shape

PostgreSQL grants PUBLIC EXECUTE on new functions globally by default. A
schema-scoped REVOKE cannot negate that global grant. The proven creator must:

1. globally revoke future function EXECUTE from PUBLIC; and
2. grant future EXECUTE to the intended principal only in the bounded schema.

The disposable proof uses `kdb_p25_creator`, `kdb_p25_target`, and
`kdb_p25_authorized`. These synthetic names are not hosted identities or a
production grant recommendation.

| Experiment | PUBLIC/anon/authenticated/service_role | intended principal | creator owner | Result |
|---|---|---|---|---|
| Direct-login creator, before correction | ALLOW through PUBLIC | ALLOW through PUBLIC | ALLOW | unsafe preimage observed |
| Direct-login creator, target schema after correction | DENY | ALLOW | ALLOW | local bounded proof |
| Same creator, wrong schema | DENY | DENY | owner-only | schema grant contained |
| Different uncorrected creator, target schema | ALLOW through PUBLIC | ALLOW through PUBLIC | other owner | `BLOCKED_UNPROVEN` |

`pg_default_acl` changes from zero creator rows to one global function row with
zero PUBLIC EXECUTE entries plus one target-schema intended-principal entry.
Reconnect and re-apply preserve the corrected result; explicit rollback
restores the observed unsafe PUBLIC preimage. Creator-role membership is empty.
A superuser `SET ROLE` session reports different `session_user`/`current_user`
and is recorded as `NOT_ACCEPTED_AS_POSITIVE`.

## Remaining gates

- `BLOCK_DEFAULT_ACL_CREATOR_HOSTED_IDENTITY`: actual hosted migration creator,
  grantor authority and current defaults are not proven.
- `BLOCK_OTHER_CREATORS`: each possible function creator needs an independently
  bounded decision; this proof never asserts blanket multi-creator closure.
- eventual production function owner transfer and membership graph are not
  admitted by this test.
- independent Security QS, hosted verification, TLS/PIAC/1Password, positive
  O1–O3 and C04/C05 remain open.

The harness also reconfirms runtime SELECT and C04 INSERT SQLSTATE `42501` and
removes all P25 roles, schemas, functions and default-ACL rows (`ZERO_RESIDUAL`).
