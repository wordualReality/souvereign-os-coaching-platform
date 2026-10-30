#!/usr/bin/env python3
"""P17 unique disposable PG17 snapshot-delta workbench readback.

Reuses the P16 TEST_FIXTURE_ADMIN two linked Source-to-Review chains.
COMMITs both, SELECTs on a new connection as baseline, then COMMITs REVOKED
on one source and re-reads as current. Delta HTML shows the unrelated case
and COUNT ONLY for the removed case. No new SQL grants. Unique target is
dropped. FINAL stays NOT_ADMITTED. Snapshot order is not attested.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_review_snapshot_delta import PACKET, snapshot_delta  # noqa: E402
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
from pg17_p14_review_inbox import (  # noqa: E402
    CAND_SHA_B,
    INSERT_B_SQL,
    REVISION_ID_B,
    RIGHTS_SHA_B,
    SELECT_B_SQL,
    SOURCE_ID_B,
    WORK_ITEM_ID_B,
    inbox_payload,
)

CASE_ID = "P17-SYNTH-PG17-DELTA"


def fail(message: str) -> None:
    raise SystemExit(message)


def ensure_protected_zero(row_counts: dict[str, int], label: str) -> None:
    for key in PROTECTED_ZERO:
        if int(row_counts.get(key, 0)) != 0:
            fail(f"P17_{label}_PROTECTED_NONEMPTY {key}={row_counts[key]}")


def main() -> None:
    refuse_hosted_env()
    target = Target("kdb_p12_" + uuid.uuid4().hex[:12])
    print("P17_IDENTITY", target.identity)
    print("P17_MODE", target.mode)
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
            fail("P17_NOT_POSTGRES_17")
        apply_stack(target)
        setup_fixture_admin(target)
        before = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(before, "BEFORE")

        commit_a = target.psql(FIXTURE_ADMIN, INSERT_SQL)
        if commit_a.returncode != 0:
            fail("P17_COMMIT_A_FAILED " + commit_a.stdout + commit_a.stderr)
        commit_b = target.psql(FIXTURE_ADMIN, INSERT_B_SQL)
        if commit_b.returncode != 0:
            fail("P17_COMMIT_B_FAILED " + commit_b.stdout + commit_b.stderr)

        snapshot_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        snapshot_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if snapshot_a.get("review_work_item") is None or snapshot_b.get("review_work_item") is None:
            fail("P17_INCOMPLETE_SNAPSHOT")

        commit = source_commit()
        baseline = inbox_payload(
            [map_candidate_chain(snapshot_a), map_candidate_chain(snapshot_b)],
            case_id=CASE_ID,
        )
        unchanged = snapshot_delta(baseline, baseline, commit=commit)
        if unchanged["delta_status"] != "PREVIEW_ONLY":
            fail("P17_EXPECTED_PREVIEW " + json.dumps({k: unchanged[k] for k in unchanged if k != "html"}))
        if unchanged["added_count"] != 0 or unchanged["removed_or_denied_count"] != 0:
            fail("P17_EXPECTED_UNCHANGED")
        if unchanged["unchanged_count"] != 2 or unchanged["visible_current_count"] != 2:
            fail("P17_EXPECTED_TWO_CURRENT")
        html_page = unchanged["html"]
        if WORK_ITEM_ID not in html_page or WORK_ITEM_ID_B not in html_page:
            fail("P17_MISSING_WORK_ITEM")
        if "<script" in html_page or "<form" in html_page or "javascript:" in html_page:
            fail("P17_UNSAFE_HTML")
        reversed_baseline = inbox_payload(
            [map_candidate_chain(snapshot_b), map_candidate_chain(snapshot_a)],
            case_id=CASE_ID,
        )
        if html_page != snapshot_delta(reversed_baseline, reversed_baseline, commit=commit)["html"]:
            fail("P17_ORDER_NOT_INVARIANT")

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
            fail("P17_REVOKE_FAILED " + revoke.stdout + revoke.stderr)
        revoked_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        fresh_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if revoked_a["source"]["rights_status"] != "REVOKED":
            fail("P17_REVOKE_NOT_COMMITTED")
        current = inbox_payload(
            [map_candidate_chain(revoked_a), map_candidate_chain(fresh_b)],
            case_id=CASE_ID,
        )
        revoked = snapshot_delta(baseline, current, commit=commit)
        if revoked["current_eligible_count"] != 1 or revoked["visible_current_count"] != 1:
            fail("P17_EXPECTED_ONE_CURRENT " + str(revoked["current_eligible_count"]))
        if revoked["baseline_eligible_count"] != 2:
            fail("P17_EXPECTED_BASELINE_TWO")
        if revoked["removed_or_denied_count"] != 1 or revoked["added_count"] != 0:
            fail("P17_EXPECTED_REMOVED_ONE")
        blob = json.dumps(revoked, sort_keys=True)
        if WORK_ITEM_ID in blob:
            fail("P17_REVOKED_ID_LEAK")
        if SOURCE_ID in blob:
            fail("P17_REVOKED_SOURCE_LEAK")
        if WORK_ITEM_ID_B not in revoked["html"]:
            fail("P17_UNRELATED_SOURCE_MISSING")
        if SOURCE_ID_B not in revoked["html"]:
            fail("P17_UNRELATED_SOURCE_ID_MISSING")
        if "POSSIBLE_CHANGE_ONLY" not in revoked["html"]:
            fail("P17_MISSING_CHANGE_LABEL")
        if "SNAPSHOT_ORDER_NOT_ATTESTED" not in revoked["html"]:
            fail("P17_MISSING_ORDER_LABEL")

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
            "baseline_eligible_count": revoked["baseline_eligible_count"],
            "current_eligible_count": revoked["current_eligible_count"],
            "removed_or_denied_count": revoked["removed_or_denied_count"],
            "delta_status": revoked["delta_status"],
            "change_authority": revoked["change_authority"],
            "snapshot_order": revoked["snapshot_order"],
            "snapshot_authority": revoked["snapshot_authority"],
            "inventory_source": revoked["inventory_source"],
            "logical_objects_claimed": revoked["logical_objects_claimed"],
            "hosted_verified": "HOSTED_VERIFIED_NO",
            "admin_db_untouched": ADMIN_DB,
            "tenant": TENANT,
            "source_commit": commit,
        }
        text = json.dumps(wrapper, sort_keys=True)
        assert_redacted(text)
        if "ALLOW" in text or "DB_COMMAND_ADMITTED" in text or "18/18" in text:
            fail("P17_FORBIDDEN_TOKEN")
        if WORK_ITEM_ID in text:
            fail("P17_WRAPPER_REVOKED_ID")
        print(text)
        print("PASS_P17_OFFLINE_SNAPSHOT_DELTA_WORKBENCH")
    finally:
        if created:
            teardown(target)
            print("P17_TEARDOWN", target.identity, "ZERO_RESIDUAL")


if __name__ == "__main__":
    main()
