# KDB-P4-INDEPENDENT-ORACLE-REPAIR-01

Issue #19. Repair/test packet only. P4 PR #15 and P5 PR #17 stay frozen.

## KDB-01

Tenant-digest binding is a separate claim from trust fail-closed and from
runtime EXECUTE denial. The disposable mutation in
`tests/kdb/pg17_p4_tenant_digest_mutation.py` corrupts O1 `p_tenant_scope`
inside `canonical_digest_v2` to a constant, applies that only to local
PostgreSQL 17, and requires `DIGEST_TENANT_BINDING_BROKEN`. The shipped
P4 SQL is restored in `finally`. Unexpected SQL and connection errors
are classified RED.

## KDB-02

CI continues to invoke `python3 tests/kdb/test_p4_digest_static.py`,
which calls `unittest.main()`.
`tests/kdb/prove_p4_static_fail_propagation.py` runs that entry, then a
scratch mutant that must exit nonzero.

Hosted apply remains blocked. Positive O1-O3 remains not admitted.
