#!/usr/bin/env python3
"""P14 unique disposable PG17 review-inbox readback.

COMMITs two synthetic Source-to-Review chains as TEST_FIXTURE_ADMIN, maps them
into the offline inbox, then COMMITs rights_status=REVOKED on one source and
proves that source has no remaining preview card. This is two linked rows, not
a physical many-to-many. No new SQL grants. Unique target is dropped. FINAL
stays NOT_ADMITTED.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))
from p11_snapshot_map import assert_redacted, map_candidate_chain  # noqa: E402
from pg17_p12_commit_reconnect_replay import (  # noqa: E402
    ADMIN_DB,
    COUNT_SQL,
    FIXTURE_ADMIN,
    INSERT_SQL,
    PROTECTED_ZERO,
    SELECT_SQL,
    SOURCE_ID,
    TENANT,
    Target,
    USER_RUNTIME,
    USER_SUPER,
    apply_stack,
    capture_sqlstate,
    create_unique_database,
    refuse_hosted_env,
    setup_fixture_admin,
    source_commit,
    start_unique_container,
    teardown,
)
from offline_review_inbox import PACKET, inbox  # noqa: E402

CASE_ID = "P14-SYNTH-PG17-INBOX"
SOURCE_ID_B = "11111111-1111-4111-8111-111111111112"
VERSION_ID_B = "22222222-2222-4222-8222-222222222224"
SUBMISSION_ID_B = "33333333-3333-4333-8333-333333333336"
CANDIDATE_ID_B = "44444444-4444-4444-8444-444444444445"
REVISION_ID_B = "55555555-5555-4555-8555-555555555556"
PROPOSAL_ID_B = "66666666-6666-4666-8666-666666666667"
WORK_ITEM_ID_B = "77777777-7777-4777-8777-777777777778"
CORR_ID_B = "88888888-8888-4888-8888-888888888889"
CONTENT_SHA_B = "abababababababababababababababababababababababababababababababab"
RIGHTS_SHA_B = "bcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbc"
CAND_SHA_B = "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd"
REQ_SHA_B = "dededededededededededededededededededededededededededededededede"
RIGHTS_ADMITTED = (
    '{"rights_status":"ADMITTED","rights_basis":"owner-authored-fixture",'
    '"allowed_purposes":["KNOWLEDGE_INTAKE"]}'
)
SPAN_B = '[{"source_version_id":"' + VERSION_ID_B + '","locator":"bytes:0-31"}]'
PAYLOAD = '{"title":"synthetic-candidate"}'

INSERT_B_SQL = f"""
BEGIN;
INSERT INTO kdb_governance.source (
  source_id, tenant_scope, source_class, external_locator, rights_status, owner_namespace
) VALUES (
  '{SOURCE_ID_B}', '{TENANT}', 'OWNER_AUTHORED', 'synthetic://kdb/p14/source-b', 'ADMITTED', 'KDB'
);
INSERT INTO kdb_governance.source_version (
  source_version_id, source_id, tenant_scope, content_sha256, rights_snapshot,
  rights_snapshot_sha256, media_type, source_version_no, acquired_at
) VALUES (
  '{VERSION_ID_B}', '{SOURCE_ID_B}', '{TENANT}', '{CONTENT_SHA_B}', '{RIGHTS_ADMITTED}'::jsonb,
  '{RIGHTS_SHA_B}', 'text/plain', 1, '2026-10-28T00:00:00Z'
);
INSERT INTO kdb_staging.submission (
  submission_id, tenant_scope, origin_owner, idempotency_key, request_sha256,
  principal_context_ref, access_decision_ref, purpose, source_version_id, status
) VALUES (
  '{SUBMISSION_ID_B}', '{TENANT}', 'KDB', 'p14-inbox-002', '{REQ_SHA_B}',
  'piac-ref-untrusted-string', 'access-ref-untrusted-string', 'KNOWLEDGE_INTAKE',
  '{VERSION_ID_B}', 'RECORDED'
);
INSERT INTO kdb_staging.candidate_revision (
  candidate_revision_id, candidate_id, revision_no, tenant_scope, source_version_id,
  submission_id, proposal_command_id, content_sha256, evidence_span_refs,
  proposal_payload, validation_state, review_state
) VALUES (
  '{REVISION_ID_B}', '{CANDIDATE_ID_B}', 1, '{TENANT}', '{VERSION_ID_B}',
  '{SUBMISSION_ID_B}', '{PROPOSAL_ID_B}', '{CAND_SHA_B}', '{SPAN_B}'::jsonb,
  '{PAYLOAD}'::jsonb, 'STRUCTURE_VALIDATED', 'PENDING_REVIEW'
);
INSERT INTO kdb_staging.review_work_item (
  review_work_item_id, candidate_revision_id, tenant_scope, owner_queue, state, correlation_id
) VALUES (
  '{WORK_ITEM_ID_B}', '{REVISION_ID_B}', '{TENANT}', 'KDB_HUMAN_REVIEW', 'REQUESTED', '{CORR_ID_B}'
);
COMMIT;
"""

SELECT_B_SQL = f"""
SELECT jsonb_build_object(
  'source', (SELECT to_jsonb(s) FROM kdb_governance.source s WHERE source_id = '{SOURCE_ID_B}'),
  'source_version', (SELECT to_jsonb(v) FROM kdb_governance.source_version v WHERE source_version_id = '{VERSION_ID_B}'),
  'submission', (SELECT to_jsonb(x) FROM kdb_staging.submission x WHERE submission_id = '{SUBMISSION_ID_B}'),
  'candidate_revision', (SELECT to_jsonb(c) FROM kdb_staging.candidate_revision c WHERE candidate_revision_id = '{REVISION_ID_B}'),
  'review_work_item', (SELECT to_jsonb(w) FROM kdb_staging.review_work_item w WHERE review_work_item_id = '{WORK_ITEM_ID_B}')
);
"""


def fail(message: str) -> None:
    raise SystemExit(message)


def ensure_protected_zero(row_counts: dict[str, int], label: str) -> None:
    for key in PROTECTED_ZERO:
        if int(row_counts.get(key, 0)) != 0:
            fail(f"P14_{label}_PROTECTED_NONEMPTY {key}={row_counts[key]}")


def inbox_payload(chains: list[dict], *, case_id: str = CASE_ID) -> dict:
    entries = []
    for index, chain in enumerate(chains):
        entries.append(
            {
                "case_id": f"{case_id}-{index + 1}",
                "expected_tenant_scope": TENANT,
                "candidate_chain": chain,
            }
        )
    return {
        "snapshot_case_id": case_id,
        "tenant_scope": TENANT,
        "entries": entries,
    }


def main() -> None:
    refuse_hosted_env()
    target = Target("kdb_p12_" + uuid.uuid4().hex[:12])
    print("P14_IDENTITY", target.identity)
    print("P14_MODE", target.mode)
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
            fail("P14_NOT_POSTGRES_17")
        apply_stack(target)
        setup_fixture_admin(target)
        before = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(before, "BEFORE")

        commit_proc = target.psql(FIXTURE_ADMIN, INSERT_SQL)
        if commit_proc.returncode != 0:
            fail("P14_COMMIT_A_FAILED " + commit_proc.stdout + commit_proc.stderr)
        commit_b = target.psql(FIXTURE_ADMIN, INSERT_B_SQL)
        if commit_b.returncode != 0:
            fail("P14_COMMIT_B_FAILED " + commit_b.stdout + commit_b.stderr)

        snapshot_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        snapshot_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if snapshot_a.get("review_work_item") is None or snapshot_b.get("review_work_item") is None:
            fail("P14_INCOMPLETE_SNAPSHOT")
        if snapshot_a["source"]["rights_status"] != "ADMITTED":
            fail("P14_SOURCE_A_NOT_COMMITTED")
        if snapshot_b["source"]["rights_status"] != "ADMITTED":
            fail("P14_SOURCE_B_NOT_COMMITTED")

        commit = source_commit()
        chain_a = map_candidate_chain(snapshot_a)
        chain_b = map_candidate_chain(snapshot_b)
        admitted = inbox(inbox_payload([chain_a, chain_b]), commit=commit)
        if admitted["inbox_status"] != "PREVIEW_ONLY":
            fail("P14_EXPECTED_PREVIEW " + json.dumps(admitted, sort_keys=True))
        if admitted["card_count"] != 2:
            fail("P14_EXPECTED_TWO_CARDS " + str(admitted["card_count"]))
        if admitted["final_authority"] != "NOT_ADMITTED":
            fail("P14_FALSE_ADMIT")
        if admitted["assignment"] != "NOT_ASSIGNED":
            fail("P14_FALSE_ASSIGN")
        ids = [card["review_work_item_id"] for card in admitted["cards"]]
        if ids != sorted(ids):
            fail("P14_CARDS_UNSORTED")
        reversed_receipt = inbox(inbox_payload([chain_b, chain_a]), commit=commit)
        if json.dumps(admitted, sort_keys=True, separators=(",", ":")) != json.dumps(
            reversed_receipt, sort_keys=True, separators=(",", ":")
        ):
            fail("P14_ORDER_NOT_INVARIANT")

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
            fail("P14_REVOKE_FAILED " + revoke.stdout + revoke.stderr)
        revoked_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        fresh_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if revoked_a["source"]["rights_status"] != "REVOKED":
            fail("P14_REVOKE_NOT_COMMITTED")
        if fresh_b["source"]["rights_status"] != "ADMITTED":
            fail("P14_SOURCE_B_REVOKED")
        revoked_receipt = inbox(
            inbox_payload([map_candidate_chain(revoked_a), map_candidate_chain(fresh_b)]),
            commit=commit,
        )
        if revoked_receipt["card_count"] != 1:
            fail("P14_EXPECTED_ONE_CARD " + str(revoked_receipt["card_count"]))
        remaining = revoked_receipt["cards"][0]
        if remaining["source_id"] == SOURCE_ID:
            fail("P14_REVOKED_SOURCE_STILL_HAS_CARD")
        if remaining["source_id"] != SOURCE_ID_B:
            fail("P14_WRONG_REMAINING_SOURCE")
        if SOURCE_ID in json.dumps(revoked_receipt["cards"]):
            fail("P14_REVOKED_IDENTITY_ON_CARDS")
        if revoked_receipt["deny_counts"] != [{"code": "REVOKED_SOURCE", "count": 1}]:
            fail("P14_REVOKE_DENY_MISMATCH " + json.dumps(revoked_receipt["deny_counts"]))
        if revoked_receipt["final_authority"] != "NOT_ADMITTED":
            fail("P14_FALSE_ADMIT_AFTER_REVOKE")

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
            "admitted_card_count": admitted["card_count"],
            "revoked_card_count": revoked_receipt["card_count"],
            "revoked_deny": "REVOKED_SOURCE",
            "snapshot_authority": admitted["snapshot_authority"],
            "inventory_source": admitted["inventory_source"],
            "logical_objects_claimed": admitted["logical_objects_claimed"],
            "hosted_verified": "HOSTED_VERIFIED_NO",
            "admin_db_untouched": ADMIN_DB,
            "source_commit": commit,
        }
        text = json.dumps(wrapper, sort_keys=True)
        assert_redacted(text)
        if "ALLOW" in text or "DB_COMMAND_ADMITTED" in text or "18/18" in text:
            fail("P14_FORBIDDEN_TOKEN")
        if "many-to-many" in text.lower():
            fail("P14_FALSE_MANY_TO_MANY")
        print(text)
        print("PASS_P14_OFFLINE_REVIEW_INBOX_READMODEL")
    finally:
        if created:
            teardown(target)
            print("P14_TEARDOWN", target.identity, "ZERO_RESIDUAL")


if __name__ == "__main__":
    main()
