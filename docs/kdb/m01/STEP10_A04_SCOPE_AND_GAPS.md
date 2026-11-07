# A04 local recovery source readiness — incomplete, not admission

This candidate is **DISPOSABLE_ONLY / HOSTED_NOT_AUTHORIZED**. The SQL file is
not a hosted migration. Its database-name, server-version and temporary-table
guards are local safety checks, not target authentication or a security
boundary against privileged operators. The foundation step creates no O1/O2/O3
command functions; the later P3/P4 derivative steps create three functions
that remain inaccessible to PUBLIC and the synthetic runtime. The existing
immutable SQL001 supplies the table definitions; the
candidate pins its own full SQL bytes separately in the versioned manifest.
Fresh roles are created only when absent; an existing role aborts rather than
being silently reused. Runtime is NOLOGIN and denied digest EXECUTE.

The local parser accepts only versioned **synthetic** exports. The newer
catalog exporter captures scoped schemas, relations, RLS and policies, roles,
memberships, grantors, effective runtime visibility, function/default ACLs,
pgcrypto, synthetic migration metadata and only a protocol row count. Its
fixture was captured from the disposable harness and is not an authoritative
hosted catalog baseline. The older comparison fixture includes invented ACL
placeholders. Its six version/name/length/MD5 rows are identity metadata,
not authenticity signatures. The old ujdz text fixtures and preimage JSON are
historical, superseded and non-routing. A local match always remains
AUTHORITATIVE_TARGET_NOT_VERIFIED and APPLY_NOT_AUTHORIZED.

The disposable test uses a Docker container with network mode none, a dedicated
database name and synthetic data only. It tests transaction-abort restoration
of a limited catalog snapshot, twelve tables with forced RLS and owner, runtime
EXECUTE denial, local digest vectors, legacy fixture row and ledger preservation,
existing-role rejection and an alternative creator's PUBLIC default function
EXECUTE. It does not establish complete raw-ACL parity, cross-session or
postcommit restoration, all object/privilege inventories, a production backup,
real runner identity, or separate independent P25/security review.

The isolated fresh pgcrypto installation had PUBLIC digest EXECUTE by default;
the harness explicitly revokes it inside the disposable database before applying
this candidate. The candidate refuses a PUBLIC-callable digest function and
grants its synthetic command owner only the scoped extension access it needs.
This is not evidence of actual hosted extension privileges. Complete guarded
disposable P3/P4 derivatives use qualified extensions.digest and retain
fail-closed command ACLs; a local test compares v2 null/blank/delimiter
semantics. No hosted compatibility or signed PIAC claim follows.

Before any separately authorized live mutation: obtain authenticated management
binding for the exact target and authoritative read-only object/role/ACL,
default-ACL and grantor export; compare its complete scoped inventory and exact
six historical fingerprints; independently verify runner/creator identity,
membership attributes and restricted extension access; obtain tested immutable
backup and postcommit restore; verify signed PIAC, tenant and replay behavior;
conduct separate non-author independent P25/security review; and obtain explicit
founder authorization for the precise hosted action. These prerequisites remain
open. BL-KDB-02 OPEN, BL-KDB-03 TO_CLARIFY, NOT_ADMITTED, NOT_SECURITY_PASS.
