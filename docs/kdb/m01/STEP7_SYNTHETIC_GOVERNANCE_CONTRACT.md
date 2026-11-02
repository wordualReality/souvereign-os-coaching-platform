# Step 7 synthetic governance contract v1 — OFFLINE ONLY

Status: `PREVIEW_ONLY / SYNTHETIC_FIXTURE / NOT_PRODUCTION_ADMITTED / HOSTED_VERIFIED_NO`. No real reviewer, signed approval, identity proof, source custody, license or authorization is attested. `TEST_ONLY:` signature and reviewer references are labels, not cryptographic verification. Fixture admin is an elevated disposable test principal, not a KDB runtime grant or production RPC.

| Object | SQL relation | Local status |
| --- | --- | --- |
| Source and version | `kdb_governance.source`, `source_version` | Existing schema; synthetic bytes hashed |
| Candidate and handoff | `kdb_staging.candidate_revision`, `review_work_item` | Existing schema; synthetic linked rows |
| C04 | `kdb_governance.human_review_decision` | Test-only decision row; no admitted human write API |
| C05 | `kdb_canonical.protocol`, `protocol_version` | Test-only row linked to exact revision and decision |
| Lifecycle | `kdb_canonical.lifecycle_event` | One test-only PUBLISHED row; no outbox event |

The fixture guard requires synthetic designation, admitted rights, purpose, source bytes and hash, candidate bytes and digest, evidence and rights bytes and digests, matching tenant and revision, test-only reviewer/authority/signature references, an approved decision, version one and a first PUBLISHED transition. Same-envelope replay returns a no-op; conflicting replay and revoked rights fail closed. These are Python fixture checks, not database-enforced production controls; references and fixture rights bytes are not authenticated claims. The SQL schema alone does not enforce every guard or check the signature, provenance semantics, content correspondence or revocation at publication time.

Before any real admission a separate reviewed contract must define authenticated human identity and authority, signed decision provenance and verification, rights/purpose and revocation freshness, evidence snapshot and source byte custody, tenant and exact candidate digest binding, immutable version numbering, idempotency storage and conflicting replay handling, ordered lifecycle rules, and database-enforced transactional checks. An O3 handoff, model suggestion or preview is never a human decision or canonical truth. No n8n activation, hosted write, real publication, or security admission follows from this fixture.
