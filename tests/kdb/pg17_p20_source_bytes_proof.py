#!/usr/bin/env python3
"""P20 unique disposable PG17 local source-bytes proof.

COMMITs two linked Source-to-Review chains whose source_version.content_sha256
is the SHA-256 of actual repo-local synthetic files. A fresh SELECT is mapped
into P14 and compared to those files. One-byte tamper denies. Committed REVOKED
rights deny the selected source while the unrelated source still matches. No new
SQL grants. Unique target is dropped. FINAL stays NOT_ADMITTED.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_source_bytes_proof import PACKET, source_bytes_proof_files  # noqa: E402
from p11_snapshot_map import assert_redacted, map_candidate_chain  # noqa: E402
from pg17_p12_commit_reconnect_replay import (  # noqa: E402
    ADMIN_DB,
    COUNT_SQL,
    FIXTURE_ADMIN,
    PROTECTED_ZERO,
    SELECT_SQL,
    SOURCE_ID,
    TENANT,
    Target,
    USER_RUNTIME,
    USER_SUPER,
    WORK_ITEM_ID,
    apply_stack,
    capture_sqlstate,
    create_unique_database,
    refuse_hosted_env,
    setup_fixture_admin,
    source_commit,
    start_unique_container,
    teardown,
)
from pg17_p12_commit_reconnect_replay import (  # noqa: E402
    CANDIDATE_ID,
    CORR_ID,
    PROPOSAL_ID,
    REVISION_ID,
    RIGHTS_ADMITTED,
    RIGHTS_SHA,
    SUBMISSION_ID,
    VERSION_ID,
    CAND_SHA,
    REQ_SHA,
)
from pg17_p14_review_inbox import (  # noqa: E402
    CAND_SHA_B,
    CANDIDATE_ID_B,
    CORR_ID_B,
    PROPOSAL_ID_B,
    REQ_SHA_B,
    REVISION_ID_B,
    RIGHTS_SHA_B,
    SELECT_B_SQL,
    SOURCE_ID_B,
    SUBMISSION_ID_B,
    VERSION_ID_B,
    WORK_ITEM_ID_B,
    inbox_payload,
)

CASE_ID = "P20-SYNTH-PG17-BYTES"
SOURCE_A = REPO / "tests" / "kdb" / "fixtures" / "p20_source_a.bin"
SOURCE_B = REPO / "tests" / "kdb" / "fixtures" / "p20_source_b.bin"


def fail(message: str) -> None:
    raise SystemExit(message)


def ensure_protected_zero(row_counts: dict[str, int], label: str) -> None:
    for key in PROTECTED_ZERO:
        if int(row_counts.get(key, 0)) != 0:
            fail(f"P20_{label}_PROTECTED_NONEMPTY {key}={row_counts[key]}")


def insert_a_sql(content_sha: str) -> str:
    span = '[{"source_version_id":"' + VERSION_ID + '","locator":"bytes:0-31"}]'
    return f"""
BEGIN;
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  '{SOURCE_ID}', '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p20/source-a', 'ADMITTED', 'KDB'
);
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '{VERSION_ID}', '{SOURCE_ID}', '{TENANT}', '{content_sha}', '{RIGHTS_ADMITTED}'::jsonb,
  '{RIGHTS_SHA}', 'text/plain', 1, '2026-10-28T00:00:00Z'
);
INSERT INTO kdb_staging.submission (
  submission_id, tenant_scope, origin_owner, idempotency_key, request_sha256,
  principal_context_ref, access_decision_ref, purpose, source_version_id, status
) VALUES (
  '{SUBMISSION_ID}', '{TENANT}', 'KDB', 'p20-bytes-001', '{REQ_SHA}',
  'piac-ref-untrusted-string', 'access-ref-untrusted-string', 'KNOWLEDGE_INTAKE',
  '{VERSION_ID}', 'RECORDED'
);
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '{REVISION_ID}', '{CANDIDATE_ID}', 1, '{TENANT}', '{VERSION_ID}',
  '{SUBMISSION_ID}', '{PROPOSAL_ID}', '{CAND_SHA}', '{span}'::jsonb,
  '{{"title":"synthetic-candidate"}}'::jsonb, 'STRUCTURE_VALIDATED', 'PENDING_REVIEW'
);
INSERT INTO kdb_staging.review_work_item (
  review_work_item_id, candidate_revision_id, tenant_scope, owner_queue, state, correlation_id
) VALUES (
  '{WORK_ITEM_ID}', '{REVISION_ID}', '{TENANT}', 'KDB_HUMAN_REVIEW', 'REQUESTED', '{CORR_ID}'
);
COMMIT;
"""


def insert_b_sql(content_sha: str) -> str:
    span = '[{"source_version_id":"' + VERSION_ID_B + '","locator":"bytes:0-31"}]'
    return f"""
BEGIN;
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  '{SOURCE_ID_B}', '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p20/source-b', 'ADMITTED', 'KDB'
);
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '{VERSION_ID_B}', '{SOURCE_ID_B}', '{TENANT}', '{content_sha}', '{RIGHTS_ADMITTED}'::jsonb,
  '{RIGHTS_SHA_B}', 'text/plain', 1, '2026-10-28T00:00:00Z'
);
INSERT INTO kdb_staging.submission (
  submission_id, tenant_scope, origin_owner, idempotency_key, request_sha256,
  principal_context_ref, access_decision_ref, purpose, source_version_id, status
) VALUES (
  '{SUBMISSION_ID_B}', '{TENANT}', 'KDB', 'p20-bytes-002', '{REQ_SHA_B}',
  'piac-ref-untrusted-string', 'access-ref-untrusted-string', 'KNOWLEDGE_INTAKE',
  '{VERSION_ID_B}', 'RECORDED'
);
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '{REVISION_ID_B}', '{CANDIDATE_ID_B}', 1, '{TENANT}', '{VERSION_ID_B}',
  '{SUBMISSION_ID_B}', '{PROPOSAL_ID_B}', '{CAND_SHA_B}', '{span}'::jsonb,
  '{{"title":"synthetic-candidate"}}'::jsonb, 'STRUCTURE_VALIDATED', 'PENDING_REVIEW'
);
INSERT INTO kdb_staging.review_work_item (
  review_work_item_id, candidate_revision_id, tenant_scope, owner_queue, state, correlation_id
) VALUES (
  '{WORK_ITEM_ID_B}', '{REVISION_ID_B}', '{TENANT}', 'KDB_HUMAN_REVIEW', 'REQUESTED', '{CORR_ID_B}'
);
COMMIT;
"""


def main() -> None:
    refuse_hosted_env()
    bytes_a = SOURCE_A.read_bytes()
    bytes_b = SOURCE_B.read_bytes()
    sha_a = hashlib.sha256(bytes_a).hexdigest()
    sha_b = hashlib.sha256(bytes_b).hexdigest()
    if sha_a == sha_b:
        fail("P20_FIXTURE_SHA_COLLISION")
    target = Target("kdb_p12_" + uuid.uuid4().hex[:12])
    print("P20_IDENTITY", target.identity)
    print("P20_MODE", target.mode)
    created = False
    try:
        if target.mode == "docker":
            start_unique_container(target)
        else:
            create_unique_database(target)
        created = True
        ver = target.must(USER_SUPER, "SHOW server_version;")
        print("server_version", ver)
        if "17." not in ver:
            fail("P20_NOT_POSTGRES_17")
        apply_stack(target)
        setup_fixture_admin(target)
        before = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(before, "BEFORE")

        commit_a = target.psql(FIXTURE_ADMIN, insert_a_sql(sha_a))
        if commit_a.returncode != 0:
            fail("P20_COMMIT_A_FAILED " + commit_a.stdout + commit_a.stderr)
        commit_b = target.psql(FIXTURE_ADMIN, insert_b_sql(sha_b))
        if commit_b.returncode != 0:
            fail("P20_COMMIT_B_FAILED " + commit_b.stdout + commit_b.stderr)

        snapshot_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        snapshot_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if snapshot_a.get("review_work_item") is None or snapshot_b.get("review_work_item") is None:
            fail("P20_INCOMPLETE_SNAPSHOT")
        if str(snapshot_a["source_version"]["content_sha256"]).lower() != sha_a:
            fail("P20_DECLARED_SHA_NOT_FROM_BYTES")

        commit = source_commit()
        payload = inbox_payload(
            [map_candidate_chain(snapshot_a), map_candidate_chain(snapshot_b)],
            case_id=CASE_ID,
        )
        with tempfile.TemporaryDirectory(dir=str(SOURCE_A.parent)) as raw:
            batch = Path(raw) / "p20-pg-batch.json"
            batch.write_text(json.dumps(payload), encoding="utf-8")
            matched = source_bytes_proof_files(batch, WORK_ITEM_ID, SOURCE_A, commit=commit)
            if matched["proof_status"] != "LOCAL_BYTES_MATCH_DECLARED_SHA":
                fail("P20_EXPECTED_MATCH")
            if matched["review_work_item_id"] != WORK_ITEM_ID:
                fail("P20_MATCH_WRONG_ITEM")
            tampered = Path(raw) / "p20-pg-tampered.bin"
            flipped = bytearray(bytes_a)
            flipped[-1] ^= 0x01
            tampered.write_bytes(flipped)
            denied = source_bytes_proof_files(batch, WORK_ITEM_ID, tampered, commit=commit)
            if denied["proof_status"] != "LOCAL_CONTENT_SHA_MISMATCH":
                fail("P20_EXPECTED_TAMPER_DENY")
            blob = json.dumps(denied, sort_keys=True)
            if WORK_ITEM_ID in blob or SOURCE_ID in blob or sha_a in blob:
                fail("P20_TAMPER_ID_LEAK")

        revoke = target.psql(
            FIXTURE_ADMIN,
            f"""
BEGIN;
UPDATE kdb_governance.source
SET rights_status = 'REVOKED'
WHERE source_id = '{SOURCE_ID}';
COMMIT;
SELECT rights_status FROM kdb_governance.source WHERE source_id = '{SOURCE_ID}';
""",
        )
        if revoke.returncode != 0:
            fail("P20_REVOKE_FAILED " + revoke.stdout + revoke.stderr)
        revoked_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        fresh_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if revoked_a["source"]["rights_status"] != "REVOKED":
            fail("P20_REVOKE_NOT_COMMITTED")
        current = inbox_payload(
            [map_candidate_chain(revoked_a), map_candidate_chain(fresh_b)],
            case_id=CASE_ID,
        )
        with tempfile.TemporaryDirectory(dir=str(SOURCE_A.parent)) as raw:
            batch = Path(raw) / "p20-pg-revoked.json"
            batch.write_text(json.dumps(current), encoding="utf-8")
            blocked = source_bytes_proof_files(batch, WORK_ITEM_ID, SOURCE_A, commit=commit)
            if blocked["proof_status"] != "PROOF_DENIED":
                fail("P20_EXPECTED_REVOKE_DENY")
            if WORK_ITEM_ID in json.dumps(blocked):
                fail("P20_REVOKED_ID_LEAK")
            other = source_bytes_proof_files(batch, WORK_ITEM_ID_B, SOURCE_B, commit=commit)
            if other["proof_status"] != "LOCAL_BYTES_MATCH_DECLARED_SHA":
                fail("P20_UNRELATED_SOURCE_NOT_MATCH")
            if other["review_work_item_id"] != WORK_ITEM_ID_B:
                fail("P20_UNRELATED_SOURCE_MISSING")
            mapped_b_sha = str(fresh_b["source_version"]["content_sha256"]).lower()
            if mapped_b_sha != sha_b:
                fail("P20_B_DECLARED_SHA_NOT_FROM_BYTES")

        capture_sqlstate(
            target,
            USER_RUNTIME,
            "PERFORM 1 FROM kdb_governance.source;",
            "42501",
            "runtime_select_denied",
        )
        capture_sqlstate(
            target,
            FIXTURE_ADMIN,
            f"""
INSERT INTO kdb_governance.human_review_decision (
  candidate_revision_id, candidate_content_sha256, reviewer_principal_ref,
  access_decision_ref, decision, source_rights_digest, review_evidence_sha256
) VALUES (
  '{REVISION_ID_B}', '{CAND_SHA_B}', 'reviewer-untrusted',
  'access-ref-untrusted-string', 'APPROVED_FOR_PROMOTION', '{RIGHTS_SHA_B}', '{CAND_SHA_B}'
);
""",
            "42501",
            "c04_insert_denied",
        )

        after = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(after, "AFTER")
        wrapper = {
            "packet": PACKET,
            "df_adoption": "DF-20261029-01",
            "gate": "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "assignment": "NOT_ASSIGNED",
            "publication": "NOT_PUBLISHED",
            "c04_human_decision": "NOT_WRITTEN",
            "c05_canonical_admission": "NOT_WRITTEN",
            "outbox": "NOT_EMITTED",
            "fixture_admin_is_runtime_principal": False,
            "physical_scope": "TWO_LINKED_SOURCE_TO_REVIEW_CHAINS",
            "proof_status_match": "LOCAL_BYTES_MATCH_DECLARED_SHA",
            "proof_status_tamper": "LOCAL_CONTENT_SHA_MISMATCH",
            "proof_status_revoked": "PROOF_DENIED",
            "inventory_source": "UNCONFIRMED_ATC10_CANDIDATES",
            "logical_objects_claimed": "NOT_18_OF_18",
            "hosted_verified": "HOSTED_VERIFIED_NO",
            "admin_db_untouched": ADMIN_DB,
            "tenant": TENANT,
            "source_commit": commit,
        }
        text = json.dumps(wrapper, sort_keys=True)
        assert_redacted(text)
        if "ALLOW" in text or "DB_COMMAND_ADMITTED" in text or "18/18" in text:
            fail("P20_FORBIDDEN_TOKEN")
        if WORK_ITEM_ID in text:
            fail("P20_WRAPPER_REVOKED_ID")
        print(text)
        print("PASS_P20_OFFLINE_SOURCE_BYTES_EVIDENCE_PROOF")
    finally:
        if created:
            teardown(target)
            print("P20_TEARDOWN", target.identity, "ZERO_RESIDUAL")


if __name__ == "__main__":
    main()
