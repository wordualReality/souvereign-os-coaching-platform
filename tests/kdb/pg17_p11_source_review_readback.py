#!/usr/bin/env python3
"""P11 disposable PG17 Source-to-Review fixture readback.

TEST_FIXTURE_ADMIN inserts synthetic O1-O3 rows in a throwaway transaction,
SELECTs them, feeds the mapped snapshot into P10, then rolls back. C04/C05
are not written. Runtime LOGIN remains denied. FINAL is always NOT_ADMITTED.
Does not apply 004/098/P2 recovery. Does not connect to Supabase.
"""
from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))
import pg17_disposable_command_path as cmd  # noqa: E402
from offline_diagnostic import diagnose  # noqa: E402
from p11_evidence_matrix import build_matrix, verify_contract_mappings  # noqa: E402
from p11_snapshot_map import (  # noqa: E402
    assert_redacted,
    diagnostic_payload,
    id_digest,
    map_candidate_chain,
    map_without_work_item,
)
from provenance_eligibility import EligibilityError, evaluate_review_eligibility  # noqa: E402

FIXTURE_ADMIN = "kdb_test_fixture_admin"
TENANT = "TENANT_SYNTH_A"
CASE_ID = "P11-SYNTH-PG17-READBACK"
LIFECYCLE = json.loads(
    (REPO / "tests" / "kdb" / "fixtures" / "p11_synthetic_lifecycle.json").read_text()
)
COUNT_SQL = """
SELECT jsonb_build_object(
  'source', (SELECT count(*) FROM kdb_governance.source),
  'source_version', (SELECT count(*) FROM kdb_governance.source_version),
  'submission', (SELECT count(*) FROM kdb_staging.submission),
  'candidate_revision', (SELECT count(*) FROM kdb_staging.candidate_revision),
  'review_work_item', (SELECT count(*) FROM kdb_staging.review_work_item),
  'human_review_decision', (SELECT count(*) FROM kdb_governance.human_review_decision),
  'protocol', (SELECT count(*) FROM kdb_canonical.protocol),
  'protocol_version', (SELECT count(*) FROM kdb_canonical.protocol_version),
  'lifecycle_event', (SELECT count(*) FROM kdb_canonical.lifecycle_event),
  'outbox_event', (SELECT count(*) FROM kdb_ops.outbox_event),
  'command_receipt', (SELECT count(*) FROM kdb_ops.command_receipt),
  'audit_event', (SELECT count(*) FROM kdb_ops.audit_event)
);
"""
PROTECTED_ZERO = (
    "human_review_decision",
    "protocol",
    "protocol_version",
    "lifecycle_event",
    "outbox_event",
)

SOURCE_ID = "11111111-1111-4111-8111-111111111111"
VERSION_ID = "22222222-2222-4222-8222-222222222222"
VERSION_ID_2 = "22222222-2222-4222-8222-222222222223"
SUBMISSION_ID = "33333333-3333-4333-8333-333333333333"
CANDIDATE_ID = "44444444-4444-4444-8444-444444444444"
REVISION_ID = "55555555-5555-4555-8555-555555555555"
PROPOSAL_ID = "66666666-6666-4666-8666-666666666666"
WORK_ITEM_ID = "77777777-7777-4777-8777-777777777777"
CORR_ID = "88888888-8888-4888-8888-888888888888"
ORPHAN_REV = "55555555-5555-4555-8555-555555555556"
ORPHAN_CAND = "44444444-4444-4444-8444-444444444445"
ORPHAN_CMD = "66666666-6666-4666-8666-666666666667"
MALFORMED_REV = "55555555-5555-4555-8555-555555555557"
MALFORMED_CAND = "44444444-4444-4444-8444-444444444446"
MALFORMED_CMD = "66666666-6666-4666-8666-666666666668"
PENDING_SRC = "11111111-1111-4111-8111-aaaaaaaaaaa1"
REVOKED_SRC = "11111111-1111-4111-8111-aaaaaaaaaaa2"
CONTENT_SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CONTENT_SHA_2 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
RIGHTS_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
CAND_SHA = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
REQ_SHA = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
RIGHTS_ADMITTED = (
    '{"rights_status":"ADMITTED","rights_basis":"owner-authored-fixture",'
    '"allowed_purposes":["KNOWLEDGE_INTAKE"]}'
)
SPAN = '[{"source_version_id":"' + VERSION_ID + '","locator":"bytes:0-31"}]'
PAYLOAD = '{"title":"synthetic-candidate"}'


def fail(message: str) -> None:
    raise SystemExit(message)


def counts() -> dict[str, int]:
    return {key: int(value) for key, value in json.loads(cmd.must(cmd.USER_SUPER, COUNT_SQL)).items()}


def ensure_protected_zero(row_counts: dict[str, int], label: str) -> None:
    for key in PROTECTED_ZERO:
        if row_counts.get(key, 0) != 0:
            fail(f"P11_{label}_PROTECTED_NONEMPTY {key}={row_counts[key]}")


def setup_fixture_admin() -> None:
    cmd.must(
        cmd.USER_SUPER,
        f"""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{FIXTURE_ADMIN}') THEN
    CREATE ROLE {FIXTURE_ADMIN} LOGIN NOINHERIT BYPASSRLS;
  END IF;
END $$;
GRANT USAGE ON SCHEMA kdb_governance, kdb_staging TO {FIXTURE_ADMIN};
GRANT SELECT, INSERT ON kdb_governance.source, kdb_governance.source_version TO {FIXTURE_ADMIN};
GRANT SELECT, INSERT ON kdb_staging.submission, kdb_staging.candidate_revision, kdb_staging.review_work_item TO {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_governance.human_review_decision FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_canonical.protocol FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_canonical.protocol_version FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_canonical.lifecycle_event FROM {FIXTURE_ADMIN};
REVOKE ALL ON TABLE kdb_ops.outbox_event FROM {FIXTURE_ADMIN};
""",
    )


def drop_fixture_admin() -> None:
    cmd.must(
        cmd.USER_SUPER,
        f"""
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{FIXTURE_ADMIN}') THEN
    EXECUTE 'DROP OWNED BY {FIXTURE_ADMIN}';
  END IF;
END $$;
DROP ROLE IF EXISTS {FIXTURE_ADMIN};
""",
    )


def parse_sqlstate(blob: str, probe: str, expected: str) -> str:
    if "P11_UNEXPECTED_SUCCESS" in blob:
        fail(f"P11_EXPECTED_DENY {probe} succeeded: {blob}")
    marker = "P11_SQLSTATE="
    if marker not in blob:
        fail(f"P11_NO_SQLSTATE {probe}: {blob}")
    state = blob.split(marker, 1)[1].split()[0].strip().rstrip('"').rstrip("'")
    if state != expected:
        fail(f"P11_SQLSTATE_MISMATCH {probe} expected={expected} got={state} blob={blob}")
    print(f"NEG {probe} SQLSTATE={state}")
    return state


def capture_sqlstate(user: str, inner_sql: str, expected: str, probe: str) -> str:
    wrapped = f"""
DO $p11$
BEGIN
  BEGIN
    {inner_sql}
    RAISE EXCEPTION 'P11_UNEXPECTED_SUCCESS {probe}';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM LIKE 'P11_UNEXPECTED_SUCCESS%' THEN
      RAISE;
    END IF;
    IF SQLSTATE IS DISTINCT FROM {cmd.psql_str(expected)} THEN
      RAISE EXCEPTION 'P11_WRONG_SQLSTATE probe={probe} expected={expected} got=% err=%', SQLSTATE, SQLERRM;
    END IF;
    RAISE EXCEPTION 'P11_SQLSTATE=%', SQLSTATE;
  END;
END
$p11$;
"""
    proc = cmd.psql(user, wrapped)
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        fail(f"P11_EXPECTED_DENY {probe} succeeded: {blob}")
    return parse_sqlstate(blob, probe, expected)


def capture_constraint(probe: str, expected: str, failing_sql: str) -> str:
    wrapped = f"""
BEGIN;
{SEED_SQL}
DO $p11$
BEGIN
  BEGIN
    {failing_sql}
    RAISE EXCEPTION 'P11_UNEXPECTED_SUCCESS {probe}';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM LIKE 'P11_UNEXPECTED_SUCCESS%' THEN
      RAISE;
    END IF;
    IF SQLSTATE IS DISTINCT FROM {cmd.psql_str(expected)} THEN
      RAISE EXCEPTION 'P11_WRONG_SQLSTATE probe={probe} expected={expected} got=% err=%', SQLSTATE, SQLERRM;
    END IF;
    RAISE EXCEPTION 'P11_SQLSTATE=%', SQLSTATE;
  END;
END
$p11$;
"""
    proc = cmd.psql(FIXTURE_ADMIN, wrapped)
    blob = proc.stdout + proc.stderr
    if proc.returncode == 0:
        fail(f"P11_EXPECTED_DENY {probe} succeeded: {blob}")
    return parse_sqlstate(blob, probe, expected)


FIXTURE_SQL = f"""
BEGIN;
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  '{SOURCE_ID}', '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p11/source', 'ADMITTED', 'KDB'
);
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '{VERSION_ID}', '{SOURCE_ID}', '{TENANT}', '{CONTENT_SHA}', '{RIGHTS_ADMITTED}'::jsonb,
  '{RIGHTS_SHA}', 'text/plain', 1, '2026-10-28T00:00:00Z'
);
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '{VERSION_ID_2}', '{SOURCE_ID}', '{TENANT}', '{CONTENT_SHA_2}', '{RIGHTS_ADMITTED}'::jsonb,
  '{RIGHTS_SHA}', 'text/plain', 2, '2026-10-28T01:00:00Z'
);
INSERT INTO kdb_staging.submission (
  submission_id, tenant_scope, origin_owner, idempotency_key, request_sha256,
  principal_context_ref, access_decision_ref, purpose, source_version_id, status
) VALUES (
  '{SUBMISSION_ID}', '{TENANT}', 'KDB', 'p11-readback-001', '{REQ_SHA}',
  'piac-ref-untrusted-string', 'access-ref-untrusted-string', 'KNOWLEDGE_INTAKE',
  '{VERSION_ID}', 'RECORDED'
);
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '{REVISION_ID}', '{CANDIDATE_ID}', 1, '{TENANT}', '{VERSION_ID}',
  '{SUBMISSION_ID}', '{PROPOSAL_ID}', '{CAND_SHA}', '{SPAN}'::jsonb,
  '{PAYLOAD}'::jsonb, 'STRUCTURE_VALIDATED', 'PENDING_REVIEW'
);
INSERT INTO kdb_staging.review_work_item (
  review_work_item_id, candidate_revision_id, tenant_scope, owner_queue, state, correlation_id
) VALUES (
  '{WORK_ITEM_ID}', '{REVISION_ID}', '{TENANT}', 'KDB_HUMAN_REVIEW', 'REQUESTED', '{CORR_ID}'
);
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES
  ('{PENDING_SRC}', '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p11/pending', 'PENDING', 'KDB'),
  ('{REVOKED_SRC}', '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p11/revoked', 'REVOKED', 'KDB');
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '{ORPHAN_REV}', '{ORPHAN_CAND}', 1, '{TENANT}', '{VERSION_ID}',
  '{SUBMISSION_ID}', '{ORPHAN_CMD}', '{CAND_SHA}', '{SPAN}'::jsonb,
  '{PAYLOAD}'::jsonb, 'STRUCTURE_VALIDATED', 'PENDING_REVIEW'
);
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '{MALFORMED_REV}', '{MALFORMED_CAND}', 1, '{TENANT}', '{VERSION_ID}',
  '{SUBMISSION_ID}', '{MALFORMED_CMD}', '{CAND_SHA}', '["not-a-span"]'::jsonb,
  '{PAYLOAD}'::jsonb, 'STRUCTURE_VALIDATED', 'PENDING_REVIEW'
);
SELECT jsonb_build_object(
  'source', (SELECT to_jsonb(s) FROM kdb_governance.source s WHERE source_id = '{SOURCE_ID}'),
  'source_version', (SELECT to_jsonb(v) FROM kdb_governance.source_version v WHERE source_version_id = '{VERSION_ID}'),
  'submission', (SELECT to_jsonb(x) FROM kdb_staging.submission x WHERE submission_id = '{SUBMISSION_ID}'),
  'candidate_revision', (SELECT to_jsonb(c) FROM kdb_staging.candidate_revision c WHERE candidate_revision_id = '{REVISION_ID}'),
  'review_work_item', (SELECT to_jsonb(w) FROM kdb_staging.review_work_item w WHERE review_work_item_id = '{WORK_ITEM_ID}'),
  'pending_source', (SELECT to_jsonb(p) FROM kdb_governance.source p WHERE source_id = '{PENDING_SRC}'),
  'revoked_source', (SELECT to_jsonb(r) FROM kdb_governance.source r WHERE source_id = '{REVOKED_SRC}'),
  'orphan_candidate', (SELECT to_jsonb(o) FROM kdb_staging.candidate_revision o WHERE candidate_revision_id = '{ORPHAN_REV}'),
  'malformed_candidate', (SELECT to_jsonb(m) FROM kdb_staging.candidate_revision m WHERE candidate_revision_id = '{MALFORMED_REV}'),
  'source_version_count', (SELECT count(*) FROM kdb_governance.source_version WHERE source_id = '{SOURCE_ID}'),
  'candidate_count', (SELECT count(*) FROM kdb_staging.candidate_revision WHERE source_version_id = '{VERSION_ID}')
);
ROLLBACK;
"""

SEED_SQL = f"""
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  '{SOURCE_ID}', '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p11/source', 'ADMITTED', 'KDB'
);
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '{VERSION_ID}', '{SOURCE_ID}', '{TENANT}', '{CONTENT_SHA}', '{RIGHTS_ADMITTED}'::jsonb,
  '{RIGHTS_SHA}', 'text/plain', 1, '2026-10-28T00:00:00Z'
);
INSERT INTO kdb_staging.submission (
  submission_id, tenant_scope, origin_owner, idempotency_key, request_sha256,
  principal_context_ref, access_decision_ref, purpose, source_version_id, status
) VALUES (
  '{SUBMISSION_ID}', '{TENANT}', 'KDB', 'p11-readback-001', '{REQ_SHA}',
  'piac-ref-untrusted-string', 'access-ref-untrusted-string', 'KNOWLEDGE_INTAKE',
  '{VERSION_ID}', 'RECORDED'
);
"""

NEGATIVES = (
    (
        "cross_tenant_fk",
        "23503",
        f"""
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '22222222-2222-4222-8222-222222222229', '{SOURCE_ID}', 'TENANT_SYNTH_B',
  'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
  '{RIGHTS_ADMITTED}'::jsonb, '{RIGHTS_SHA}', 'text/plain', 2, '2026-10-28T00:00:00Z'
);
""",
    ),
    (
        "duplicate_source_version_no",
        "23505",
        f"""
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '22222222-2222-4222-8222-222222222228', '{SOURCE_ID}', '{TENANT}',
  'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
  '{RIGHTS_ADMITTED}'::jsonb, '{RIGHTS_SHA}', 'text/plain', 1, '2026-10-28T00:00:00Z'
);
""",
    ),
    (
        "duplicate_submission_idempotency",
        "23505",
        f"""
INSERT INTO kdb_staging.submission (
  submission_id, tenant_scope, origin_owner, idempotency_key, request_sha256,
  principal_context_ref, access_decision_ref, purpose, source_version_id, status
) VALUES (
  '33333333-3333-4333-8333-333333333339', '{TENANT}', 'KDB', 'p11-readback-001',
  'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
  'piac-ref-untrusted-string', 'access-ref-untrusted-string', 'KNOWLEDGE_INTAKE',
  '{VERSION_ID}', 'RECORDED'
);
""",
    ),
    (
        "invalid_candidate_link",
        "23503",
        f"""
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '55555555-5555-4555-8555-555555555559', '44444444-4444-4444-8444-444444444449',
  1, '{TENANT}', '22222222-2222-4222-8222-222222222229',
  '{SUBMISSION_ID}', '66666666-6666-4666-8666-666666666669', '{CAND_SHA}',
  '{SPAN}'::jsonb, '{PAYLOAD}'::jsonb, 'STRUCTURE_VALIDATED', 'PENDING_REVIEW'
);
""",
    ),
    (
        "review_item_missing_fk",
        "23503",
        f"""
INSERT INTO kdb_staging.review_work_item (
  review_work_item_id, candidate_revision_id, tenant_scope, owner_queue, state, correlation_id
) VALUES (
  '77777777-7777-4777-8777-777777777779', '55555555-5555-4555-8555-555555555559',
  '{TENANT}', 'KDB_HUMAN_REVIEW', 'REQUESTED', '{CORR_ID}'
);
""",
    ),
    (
        "empty_evidence_array",
        "23514",
        f"""
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '55555555-5555-4555-8555-555555555558', '44444444-4444-4444-8444-444444444448',
  1, '{TENANT}', '{VERSION_ID}', '{SUBMISSION_ID}',
  '66666666-6666-4666-8666-666666666661', '{CAND_SHA}', '[]'::jsonb,
  '{PAYLOAD}'::jsonb, 'STRUCTURE_VALIDATED', 'PENDING_REVIEW'
);
""",
    ),
    (
        "invalid_review_state",
        "23514",
        f"""
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '55555555-5555-4555-8555-555555555550', '44444444-4444-4444-8444-444444444440',
  1, '{TENANT}', '{VERSION_ID}', '{SUBMISSION_ID}',
  '66666666-6666-4666-8666-666666666660', '{CAND_SHA}', '{SPAN}'::jsonb,
  '{PAYLOAD}'::jsonb, 'STRUCTURE_VALIDATED', 'APPROVED_FOR_PROMOTION'
);
""",
    ),
)

FORCE_RLS_SQL = f"""
BEGIN;
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  'aaaaaaaa-bbbb-4ccc-8ddd-ffff00000001', '{TENANT}', 'OWNER_AUTHORED',
  'synthetic://kdb/p11/rls', 'ADMITTED', 'KDB'
);
SELECT 'superuser=' || count(*)::text FROM kdb_governance.source
 WHERE external_locator = 'synthetic://kdb/p11/rls';
SET ROLE kdb_command_owner;
SELECT 'command_owner_no_guc=' || count(*)::text FROM kdb_governance.source;
RESET ROLE;
ROLLBACK;
"""


def source_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return "UNPINNED_LOCAL"
    return proc.stdout.strip()


def expect_eligibility_deny(chain: dict, code: str) -> None:
    try:
        evaluate_review_eligibility(chain)
    except EligibilityError as exc:
        if exc.code != code:
            fail(f"P11_P08_CODE expected={code} got={exc.code}")
        print(f"P08_DENY {code}")
        return
    fail(f"P11_P08_EXPECTED_DENY {code}")


def main() -> None:
    cmd.ensure_container()
    cmd.ensure_schema()
    setup_fixture_admin()
    try:
        before = counts()
        ensure_protected_zero(before, "BEFORE")
        print("ROW_COUNTS_BEFORE", json.dumps(before, sort_keys=True))

        proc = cmd.psql(FIXTURE_ADMIN, FIXTURE_SQL)
        if proc.returncode != 0:
            fail("P11_FIXTURE_SELECT_FAILED " + proc.stdout + proc.stderr)
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        if not lines:
            fail("P11_EMPTY_SNAPSHOT")
        snapshot = json.loads(lines[-1])
        if snapshot.get("source") is None or snapshot.get("review_work_item") is None:
            fail("P11_INCOMPLETE_SNAPSHOT")
        if snapshot["pending_source"]["rights_status"] != "PENDING":
            fail("P11_PENDING_NOT_PERSISTED_IN_TXN")
        if snapshot["revoked_source"]["rights_status"] != "REVOKED":
            fail("P11_REVOKED_NOT_PERSISTED_IN_TXN")
        if int(snapshot.get("source_version_count") or 0) < 2:
            fail("P11_SOURCE_VERSION_NOT_ONE_TO_N")
        if int(snapshot.get("candidate_count") or 0) < 2:
            fail("P11_CANDIDATE_NOT_ONE_TO_N")
        mappings = verify_contract_mappings(snapshot)

        chain = map_candidate_chain(snapshot)
        payload = diagnostic_payload(
            case_id=CASE_ID,
            expected_tenant_scope=TENANT,
            candidate_chain=chain,
            lifecycle_chain=LIFECYCLE,
        )
        original = deepcopy(payload)
        receipt = diagnose(payload, commit=source_commit())
        if payload != original:
            fail("P11_INPUT_MUTATED")
        if receipt["final_authority"] != "NOT_ADMITTED":
            fail("P11_FALSE_ADMIT")
        if receipt["execution"] != "NON_EXECUTABLE":
            fail("P11_FALSE_EXECUTABLE")
        if receipt["c04_human_decision"] != "NOT_WRITTEN":
            fail("P11_FALSE_C04")
        if receipt["c05_canonical_admission"] != "NOT_WRITTEN":
            fail("P11_FALSE_C05")
        if receipt["stages"]["c04_c05_transition"]["status"] != "ABSENT":
            fail("P11_FALSE_C04_C05_STAGE")
        if receipt["stages"]["tenant_scope"]["status"] != "STAGE_LOCAL_ELIGIBLE":
            fail("P11_TENANT_STAGE " + receipt["stages"]["tenant_scope"]["code"])
        if receipt["stages"]["provenance"]["status"] != "STAGE_LOCAL_ELIGIBLE":
            fail("P11_PROVENANCE_STAGE " + receipt["stages"]["provenance"]["code"])
        if receipt["stages"]["lifecycle"]["status"] != "STAGE_LOCAL_ELIGIBLE":
            fail("P11_LIFECYCLE_STAGE " + receipt["stages"]["lifecycle"]["code"])

        revoked = deepcopy(chain)
        revoked["source"]["rights_status"] = "REVOKED"
        expect_eligibility_deny(revoked, "REVOKED_SOURCE")
        pending = deepcopy(chain)
        pending["source"]["rights_status"] = "PENDING"
        expect_eligibility_deny(pending, "MISSING_RIGHTS")

        malformed = deepcopy(chain)
        malformed["candidate_revision"]["evidence_span_refs"] = snapshot["malformed_candidate"][
            "evidence_span_refs"
        ]
        expect_eligibility_deny(malformed, "MALFORMED_EVIDENCE_SPAN")
        expect_eligibility_deny(map_without_work_item(snapshot), "MISSING_REVIEW_WORK_ITEM")

        negatives = []
        for probe, sqlstate, sql in NEGATIVES:
            state = capture_constraint(probe, sqlstate, sql)
            negatives.append({"probe": probe, "sqlstate": state, "enforced_by": "DB_CONSTRAINT"})

        c04_state = capture_sqlstate(
            FIXTURE_ADMIN,
            f"""
INSERT INTO kdb_governance.human_review_decision (
  candidate_revision_id, candidate_content_sha256, reviewer_principal_ref,
  access_decision_ref, decision, source_rights_digest, review_evidence_sha256
) VALUES (
  '{REVISION_ID}', '{CAND_SHA}', 'reviewer-untrusted',
  'access-ref-untrusted-string', 'APPROVED_FOR_PROMOTION', '{RIGHTS_SHA}', '{CAND_SHA}'
);
""",
            "42501",
            "c04_insert_denied",
        )
        negatives.append({"probe": "c04_insert_denied", "sqlstate": c04_state, "enforced_by": "ACL"})

        runtime = []
        for probe, sql in (
            ("runtime_select_denied", "PERFORM 1 FROM kdb_governance.source;"),
            (
                "runtime_insert_denied",
                f"""
INSERT INTO kdb_governance.source (
  tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p11/runtime', 'ADMITTED', 'KDB'
);
""",
            ),
            ("runtime_security_context_execute_denied", "PERFORM kdb_ops.security_context_ready();"),
            (
                "runtime_o1_execute_denied",
                "PERFORM kdb_ops.ingest_source("
                " '11111111-1111-4111-8111-999999999999'::uuid,"
                f" '{SUBMISSION_ID}'::uuid, '{TENANT}', 'KDB', 'p11-runtime-001',"
                f" '{REQ_SHA}', 'OWNER_AUTHORED', 'synthetic://kdb/p11/runtime',"
                f" '{CONTENT_SHA}', '{RIGHTS_ADMITTED}'::jsonb, '{RIGHTS_SHA}',"
                " 'piac-ref-untrusted-string', 'access-ref-untrusted-string',"
                f" 'KNOWLEDGE_INTAKE', '{CORR_ID}'::uuid, '2026-10-28T00:00:00Z'::timestamptz"
                ");",
            ),
        ):
            state = capture_sqlstate(cmd.USER_RUNTIME, sql, "42501", probe)
            runtime.append(
                {
                    "probe": probe,
                    "sqlstate": state,
                    "role": cmd.USER_RUNTIME,
                    "enforced_by": "ACL",
                }
            )

        rls = cmd.psql(cmd.USER_SUPER, FORCE_RLS_SQL)
        if rls.returncode != 0:
            fail("P11_FORCE_RLS_FAILED " + rls.stdout + rls.stderr)
        rls_out = rls.stdout + rls.stderr
        if "superuser=1" not in rls_out:
            fail("P11_FORCE_RLS_SUPERUSER_MISSING " + rls_out)
        if "command_owner_no_guc=0" not in rls_out:
            fail("P11_FORCE_RLS_LEAK " + rls_out)
        print("FORCE_RLS command_owner_no_guc=0 SET_ROLE_FROM_SUPERUSER_IS_NOT_A_POSITIVE")

        after = counts()
        print("ROW_COUNTS_AFTER", json.dumps(after, sort_keys=True))
        if after != before:
            fail(f"P11_RESIDUAL before={before} after={after}")
        ensure_protected_zero(after, "AFTER")
        if after.get("command_receipt", 0) != before.get("command_receipt", 0):
            fail("P11_NEW_COMMAND_RECEIPT")
        if after.get("audit_event", 0) != before.get("audit_event", 0):
            fail("P11_NEW_AUDIT_EVENT")
        commit = source_commit()
        matrix = build_matrix(
            commit=commit,
            environment="disposable-postgres-17",
            run={
                "slice_pass": True,
                "denials_pass": True,
                "zero_ops": True,
                "tests": [
                    "pg17_p11_source_review_readback",
                    "test_p11_source_review_readback",
                    "test_offline_diagnostic",
                ],
                "contract_mappings": mappings,
                "cardinality": {
                    "source_version_per_source": int(snapshot.get("source_version_count") or 0),
                    "candidates_per_bound_version": int(snapshot.get("candidate_count") or 0),
                },
            },
        )
        if matrix["logical_objects_claimed"] == "18/18":
            fail("P11_FALSE_18_OF_18")
        if matrix["inventory_source"] != "INVENTORY_SOURCE_GAP":
            fail("P11_INVENTORY_MUST_STAY_GAP")
        if matrix["hosted_verified"] != "HOSTED_VERIFIED_NO":
            fail("P11_FALSE_HOSTED")

        wrapper = {
            "packet": "KDB-M01-P11-DISPOSABLE-PG17-SOURCE-TO-REVIEW-READBACK-01",
            "df_adoption": "DF-20261029-01",
            "gate": "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "fixture_admin": FIXTURE_ADMIN,
            "persistence": "DISPOSABLE_PG17_TRANSACTION_ROLLED_BACK",
            "lifecycle_source": "SYNTHETIC_FIXTURE_NOT_DB",
            "c04_human_decision": "NOT_WRITTEN",
            "c05_canonical_admission": "NOT_WRITTEN",
            "outbox": "NOT_EMITTED",
            "content_digest_proof": "OPAQUE_SHA_UNPROVEN",
            "event_watermark": "UNTRUSTED",
            "rollback": "ZERO_RESIDUAL",
            "snapshot_id_digest": id_digest(snapshot),
            "row_counts_before": before,
            "row_counts_after": after,
            "negatives": negatives,
            "runtime_denials": runtime,
            "force_rls": {
                "role": "kdb_command_owner",
                "missing_tenant_guc_count": 0,
                "note": "SET_ROLE_FROM_SUPERUSER_IS_NOT_A_POSITIVE",
            },
            "evidence_matrix": matrix,
            "diagnostic": receipt,
            "source_commit": commit,
        }
        text = json.dumps(wrapper, sort_keys=True)
        assert_redacted(text)
        if "ALLOW" in text or "DB_COMMAND_ADMITTED" in text:
            fail("P11_FORBIDDEN_TOKEN")
        print(text)
        print("PASS_P11_DISPOSABLE_PG17_SOURCE_TO_REVIEW_READBACK")
    finally:
        drop_fixture_admin()


if __name__ == "__main__":
    main()
