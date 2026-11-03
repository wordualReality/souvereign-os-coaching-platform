# Step 8 C04/C05 SQL falsification — local only

Status: `TEST_ONLY / NOT_ADMITTED / NOT_SECURITY_PASS`. This is not an executable migration or hosted authorization. The test-only SQL candidate lives outside migration roots, runs inside a rolled-back disposable PG17 transaction and has no SECURITY DEFINER function. Do not install it in a real environment.

| Invariant | Existing source / authority | Local SQL observation | Candidate status |
| --- | --- | --- | --- |
| Candidate digest and rights digest match C04 | Candidate and source-version rows | Wrong digests accepted when Python guard bypassed | Temporary C04 trigger rejects mismatch 23514 |
| Source rights remain ADMITTED | `source.rights_status` | Revoked rights accepted by existing schema | Temporary C04/C05 triggers reject current revoked status 23514 |
| Reviewer, authority, signed reference | External authenticated human / trusted signer | Empty references accepted by existing schema; arbitrary TEST_ONLY strings accepted | Empty text rejected locally; signature, authority and signer truth remain UNVERIFIED |
| Candidate / decision / version links | SQL001 FKs and unique constraints | FKs bind identifiers, not every semantic relationship | Temporary trigger checks C04 candidate and C05 decision/revision/digest; not an external authorization |
| Tenant isolation | SQL001 composite candidate/source/review FKs | Candidate and review tenant linkage is structural; C04 has no independent tenant field | Candidate joins existing tenant-bound rows; cross-tenant adversarial coverage remains limited |
| First lifecycle event | Existing kind CHECK and FK | Existing schema does not enforce intended sequence | Temporary test trigger accepts first PUBLISHED only; not a complete lifecycle engine |
| Durable replay | SQL001 unique constraints | Duplicate row denied 23505; lookup finds existing synthetic decision | Same command equivalence and conflict classification are not a durable RPC |
| Runtime direct write | SQL grants and schema permissions | Direct runtime denied 42501 even after temporary schema USAGE, specifically at table layer for INSERT/UPDATE/DELETE C04/C05 | No runtime table grants added; schema ACL restored |

The candidate is a narrow falsification aid, not safe production DDL: concurrent decisions, source revocation races, lock ordering, update/delete behavior, existing rows, signed decision validation, authoritative source rights, evidence-span content, tenant policy and cross-table privilege/RLS contexts need separate review and tests. The lifecycle trigger deliberately handles only the first synthetic PUBLISHED event. The fixture transaction uses a privileged disposable administrator, not an admitted human writer. An arbitrary nonempty reference is never proof of signature or authority.

Any proposed migration requires an independently reviewed PR, creator/default-ACL and ownership design, security review, exact source and rights authority, concurrency and rollback proof, and separate hosted approval. P25/P26 and SQL001–003 remain unchanged. No live database, production, n8n or merge is authorized by this artifact.
