# KDB-M01 rollback and forward-fix contract (not executable)


Before physical mutation: no rollback needed; remove uncommitted local artifact staging only.


After **schema-only** apply in isolated target, before inserting any user data: stop consumers, verify migration manifest/checksums and that all new KDB tables are empty; verify no external grants or consumers. Only after separate owner approval, reverse `003`, then `002`, then `001` via a tested signed rollback migration. No `DROP SCHEMA CASCADE` against shared legacy or production; produce object-targeted reverse DDL on the actual admitted preimage.


After durable source/candidate evidence exists: **forward-fix, never delete** immutable SourceVersion, CandidateRevision, HumanReviewDecision, ProtocolVersion, lifecycle and audit events. Disable command ingress, quarantine uncertain outcomes, preserve sequence and idempotency keys; redeploy a compatible migration after owner approval and replay synthetic tests. Never reapply R16/R18.


The **first** mutation is gated by `KDB-M01-MUTATION-GATE-A`; any actual rollback also requires its own bounded written authorization. There is no self-executing rollback.
