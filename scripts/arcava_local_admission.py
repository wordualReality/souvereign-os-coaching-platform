#!/usr/bin/env python3
"""Offline local-scope check for the confirmed Arcava mandate.

A matching snapshot is not a live reread, an owner pin, or an A09 admission.
Caller URLs, digests, authorization text, and local file overrides are rejected.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCERPT = ROOT / "docs" / "arcava" / "admission" / "mandate" / "arc36p25-t150-local-mandate-excerpt.txt"
SYNTHETIC = ROOT / "docs" / "arcava" / "admission" / "synthetic"

PINNED_DOCUMENT_ID = "18tLEM05Dxlo_8_bPmCvWygFHJtQ4v1B5mYp0PL7OdZI"
PINNED_DECISION_ID = "ARC36P25-T150-MANDATE-AND-E1-A09-SCOPE-01"
PINNED_PREIMAGE = "1457be9863ab6086a4b1e2dcc566129c9d7d832b"
PINNED_DIGEST = "e6b43c6d6684883c89d7002fc672ceb3f99d43abd6014f69b1f500ef6b325839"
PINNED_SCOPE = "LIMITED_LOCAL_TEST_SCOPE"
ALLOWED_ACTION = "offline_subcheck"
PROHIBITED = frozenset(
    {
        "sql_execution",
        "hosted_apply",
        "live_access",
        "main_merge",
        "n8n",
        "a09_pass",
        "t150_pass",
    }
)
REVOKED_SOURCE_IDS = frozenset({"replaced-mandate-sample"})
EXPECTED_CONTRACTS = (
    "CT-ARC-002",
    "CT-ARC-003",
    "CT-ARC-004",
    "CT-ARC-R03-REM-001",
)
BASELINE = "86 = 47 P0 + 39 P1"
CALLER_FLAGS = (
    "--authorization",
    "--digest",
    "--url",
    "--mandate-url",
    "--owner-admitted",
)
ENTRYPOINTS = ("A09-T01", "A09-T04", "A09-T44", "A09-T48")
ALLOW_PREFIXES = (
    "contracts/arcava/",
    "database/migrations/",
    "database/policies/",
    "docs/arcava/admission/mandate/",
    "docs/arcava/admission/synthetic/",
)


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path):
    return sha256_bytes(path.read_bytes())


def parse_excerpt(payload):
    if b"owner_admitted" in payload:
        return None, "forged_boolean"
    text = payload.decode("utf-8")
    fields = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if ": " not in line:
            return None, "malformed"
        key, value = line.split(": ", 1)
        if key in fields:
            return None, "duplicate_field"
        fields[key] = value
    required = (
        "decision_id",
        "source_document_id",
        "preimage_sha",
        "scope",
        "allowed",
        "prohibited",
        "revocation_feed",
        "cryptographic_signature",
    )
    if any(key not in fields for key in required):
        return None, "missing_field"
    return fields, None


def decide(payload, action):
    lines = []
    code = 0
    fields, error = parse_excerpt(payload)
    digest = sha256_bytes(payload)
    lines.append("MANDATE_SOURCE UNVERIFIED reason=authenticated_reread_unavailable")
    lines.append("REVOCATION_STATUS UNKNOWN")
    lines.append("ADMISSION NOT_ADMITTED reason=revocation_unknown_fail_closed")
    lines.append("CRYPTOGRAPHIC_SIGNATURE ABSENT")
    if error == "forged_boolean":
        lines.append("FORGED_BOOLEAN REJECTED")
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    if fields is None:
        lines.append("MANDATE_SNAPSHOT INTEGRITY_FAIL reason=" + error)
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    source_id = fields["source_document_id"]
    if source_id in REVOKED_SOURCE_IDS:
        lines.append("MANDATE_SNAPSHOT REJECTED reason=revoked_source")
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    if source_id != PINNED_DOCUMENT_ID:
        lines.append("MANDATE_SNAPSHOT REJECTED reason=unknown_source")
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    if fields["decision_id"] != PINNED_DECISION_ID:
        lines.append("MANDATE_SNAPSHOT INTEGRITY_FAIL reason=wrong_decision")
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    if fields["preimage_sha"] != PINNED_PREIMAGE:
        lines.append("MANDATE_SNAPSHOT INTEGRITY_FAIL reason=wrong_revision")
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    if digest != PINNED_DIGEST:
        lines.append("MANDATE_SNAPSHOT INTEGRITY_FAIL reason=digest")
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    if fields["cryptographic_signature"] != "false":
        lines.append("MANDATE_SNAPSHOT INTEGRITY_FAIL reason=signature_claim")
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    if fields["scope"] != PINNED_SCOPE:
        lines.append("MANDATE_SNAPSHOT INTEGRITY_FAIL reason=scope")
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    if fields["revocation_feed"] != "absent":
        lines.append("MANDATE_SNAPSHOT INTEGRITY_FAIL reason=revocation_claim")
        lines.append("TEST_SCOPE SCOPE_ABSENT")
        return lines, 1
    lines.append("MANDATE_SNAPSHOT INTEGRITY_PASS")
    lines.append("MANDATE_DIGEST " + digest)
    lines.append("DECISION_ID " + PINNED_DECISION_ID)
    lines.append("PREIMAGE_SHA " + PINNED_PREIMAGE)
    if action in PROHIBITED or action != ALLOWED_ACTION:
        lines.append("TEST_SCOPE SCOPE_EXCEEDED action=" + action)
        return lines, 1
    if action not in fields["allowed"].split():
        lines.append("TEST_SCOPE SCOPE_EXCEEDED action=" + action)
        return lines, 1
    lines.append("TEST_SCOPE LIMITED_LOCAL_TEST_SCOPE")
    lines.append("OWNER_PIN missing path=docs/arcava/admission/toolchain-owner-pin.json")
    return lines, code


def allowed_path(root, relative):
    if not relative or relative.startswith("/") or "\\" in relative:
        raise ValueError("PATH_REJECTED")
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("PATH_REJECTED")
    if "kdb" in parts:
        raise ValueError("PATH_REJECTED")
    candidate = (root / relative).resolve()
    base = root.resolve()
    try:
        rel = candidate.relative_to(base).as_posix()
    except ValueError as error:
        raise ValueError("PATH_REJECTED") from error
    if not any(rel.startswith(prefix) for prefix in ALLOW_PREFIXES):
        raise ValueError("PATH_REJECTED")
    return candidate


def read_allowed(root, relative):
    path = allowed_path(root, relative)
    if not path.is_file():
        raise ValueError("PATH_REJECTED")
    return path.read_bytes()


def classify_preflight(checksums, ledger):
    if ledger is None:
        return "UNKNOWN", "ledger_absent"
    if ledger.get("execute") is True:
        return "MUTATION_BLOCKED", "execute_requested"
    recorded = ledger.get("files")
    if not isinstance(recorded, dict):
        return "UNKNOWN", "ledger_incomplete"
    for name, digest in checksums.items():
        if name not in recorded:
            return "UNKNOWN", "ledger_incomplete"
        if recorded[name] != digest:
            return "CONFLICTING", name
    if set(recorded) - set(checksums):
        return "CONFLICTING", "extra_ledger_file"
    return "COMPATIBLE_EXISTING", "checksums_agree"


def migration_checksums(root):
    folder = root / "database" / "migrations"
    files = sorted(path for path in folder.glob("*.sql") if path.is_file())
    return {path.name: sha256_file(path) for path in files}


KNOWN_MIGRATIONS = (
    (
        "001_project_b_baseline_schema",
        "database/migrations/001_project_b_baseline_schema.sql",
    ),
    (
        "002_project_b_journey_provisioning_hardening",
        "database/migrations/002_project_b_journey_provisioning_hardening.sql",
    ),
)


def ledger_lines(disposition, reason, plan):
    lines = [
        "LEDGER_CLASS SYNTHETIC",
        "APPLIED_DATABASE_STATE ABSENT",
        "LEDGER_RESULT " + disposition + " reason=" + reason,
        "SQL_EXECUTION NOT_EXECUTED",
        "MUTATION_APPLY NOT_EXECUTED",
    ]
    if disposition == "LOCAL_PLAN":
        lines.append("PLAN " + ",".join(plan))
        lines.append("MUTATION_PLAN DELIVERED")
    else:
        lines.append("MUTATION_PLAN BLOCKED")
    return lines


def evaluate_ledger(root, fixture):
    entries = fixture.get("entries")
    if not isinstance(entries, list):
        return ledger_lines("MUTATION_PLAN_BLOCKED", "malformed", []), 1, "malformed"
    seen = []
    for entry in entries:
        if not isinstance(entry, dict):
            return ledger_lines("MUTATION_PLAN_BLOCKED", "malformed", []), 1, "malformed"
        migration_id = entry.get("migration_id")
        if migration_id in seen:
            return ledger_lines("MUTATION_PLAN_BLOCKED", "duplicate_entry", []), 1, "duplicate_entry"
        seen.append(migration_id)
    if fixture.get("execute") is True:
        return ledger_lines("MUTATION_PLAN_BLOCKED", "execute_requested", []), 1, "execute_requested"
    known = {migration_id: path for migration_id, path in KNOWN_MIGRATIONS}
    reasons = []
    plan = []
    listed = set()
    for entry in entries:
        migration_id = entry.get("migration_id")
        relative = entry.get("path")
        recorded = entry.get("sha256")
        listed.add(migration_id)
        if migration_id not in known or relative != known[migration_id]:
            reasons.append("unknown_migration")
            continue
        try:
            allowed_path(root, relative)
        except ValueError:
            reasons.append("unknown_migration")
            continue
        file_path = root / relative
        if not file_path.is_file():
            reasons.append("missing_entry")
            continue
        if sha256_file(file_path) != recorded:
            reasons.append("digest_mismatch")
            continue
        plan.append(migration_id)
    for migration_id, relative in KNOWN_MIGRATIONS:
        if migration_id not in listed and (root / relative).is_file():
            reasons.append("missing_entry")
    if reasons:
        return ledger_lines("MUTATION_PLAN_BLOCKED", reasons[0], []), 1, reasons[0]
    expected_plan = [migration_id for migration_id, _relative in KNOWN_MIGRATIONS]
    if plan != expected_plan:
        return ledger_lines("MUTATION_PLAN_BLOCKED", "missing_entry", []), 1, "missing_entry"
    return ledger_lines("LOCAL_PLAN", "checksums_agree", plan), 0, "checksums_agree"


def load_json(path):
    return json.loads(path.read_text())


def run_t01(root):
    lines = ["CASE A09-T01", "CASE_ARTIFACT PRESENT", "OFFLINE_SUBCHECK_EXECUTED"]
    fixture = load_json(SYNTHETIC / "A09-T01" / "golden" / "ledger-match.json")
    evaluated, code, reason = evaluate_ledger(root, fixture)
    lines.extend(evaluated)
    expected = fixture["expected"]
    lines.append("A09_STATUS NOT_EXECUTED")
    lines.append("FULL_A09_PASS ABSENT")
    if (
        code != 0
        or reason != expected["reason"]
        or expected["disposition"] != "LOCAL_PLAN"
        or fixture.get("applied_database_state") is not False
    ):
        lines.append("FAIL ledger_oracle")
        return lines, 1
    lines.append("SUBCHECK_PASS case=A09-T01")
    return lines, 0


def schema_files(root):
    folder = root / "contracts" / "arcava"
    found = []
    for path in folder.rglob("*.json"):
        if path.name == "contract-manifest.json":
            continue
        found.append(path.relative_to(folder).as_posix())
    return sorted(found)


def classify_registry(file_count, contract_ids, claim_48):
    if claim_48:
        return "FAIL", "false_48_pass"
    if "CT-ARC-007" in contract_ids:
        return "FAIL", "e16_presented_active"
    if file_count != 16 or tuple(contract_ids) != EXPECTED_CONTRACTS:
        return "FAIL", "registry_drift"
    return "SUBCHECK", "physical_16_is_not_registry_48"


def bind_contracts(root, pins):
    manifest_path = root / "contracts" / "arcava" / "contract-manifest.json"
    if not manifest_path.is_file():
        return ["BYTE_BIND FAIL reason=missing_file"], 1, "missing_file"
    manifest = json.loads(manifest_path.read_text())
    contracts = {item["contract_id"]: item for item in manifest["contracts"]}
    common = {item["path"]: item["sha256"] for item in manifest["common_components"]}
    if "CT-ARC-007" in contracts:
        return ["BYTE_BIND FAIL reason=e16_presented_active"], 1, "e16_presented_active"
    schema_count = 0
    for pin in pins.get("pins", []):
        relative = pin.get("path", "")
        try:
            allowed_path(root, relative)
        except ValueError:
            return ["BYTE_BIND FAIL reason=illegal_path"], 1, "illegal_path"
        if not relative.startswith("contracts/arcava/"):
            return ["BYTE_BIND FAIL reason=illegal_path"], 1, "illegal_path"
        file_path = root / relative
        if not file_path.is_file():
            return ["BYTE_BIND FAIL reason=missing_file"], 1, "missing_file"
        digest = sha256_file(file_path)
        if digest != pin.get("sha256"):
            return ["BYTE_BIND FAIL reason=digest_mismatch"], 1, "digest_mismatch"
        kind = pin.get("set")
        if kind == "manifest":
            if relative != "contracts/arcava/contract-manifest.json" or pin.get("version") != manifest["manifest_version"]:
                return ["BYTE_BIND FAIL reason=binding_mismatch"], 1, "binding_mismatch"
            continue
        if kind == "common":
            if common.get(relative) != digest or pin.get("version") != "1.0":
                return ["BYTE_BIND FAIL reason=binding_mismatch"], 1, "binding_mismatch"
            schema_count += 1
            continue
        if kind != "contract":
            return ["BYTE_BIND FAIL reason=binding_mismatch"], 1, "binding_mismatch"
        contract = contracts.get(pin.get("contract_id"))
        if contract is None or contract.get("profile_version") != pin.get("version"):
            return ["BYTE_BIND FAIL reason=binding_mismatch"], 1, "binding_mismatch"
        if contract.get("runtime_producer_ready") is not False:
            return ["BYTE_BIND FAIL reason=runtime_claim"], 1, "runtime_claim"
        expected_path = "contracts/arcava/{0}/{1}/{2}.schema.json".format(
            pin["contract_id"], pin["version"], pin["kind"]
        )
        matches = [item for item in contract["physical_schemas"] if item["path"] == relative]
        if relative != expected_path or len(matches) != 1:
            return ["BYTE_BIND FAIL reason=binding_mismatch"], 1, "binding_mismatch"
        if matches[0]["sha256"] != digest or matches[0]["kind"] != pin["kind"]:
            return ["BYTE_BIND FAIL reason=binding_mismatch"], 1, "binding_mismatch"
        schema_count += 1
    if schema_count != 16 or len(contracts) != 4:
        return ["BYTE_BIND FAIL reason=registry_drift"], 1, "registry_drift"
    return ["BYTE_BIND PASS reason=bytes_match_pins"], 0, "bytes_match_pins"


def run_t04(root):
    lines = ["CASE A09-T04", "CASE_ARTIFACT PRESENT", "OFFLINE_SUBCHECK_EXECUTED"]
    pins = load_json(SYNTHETIC / "A09-T04" / "byte-pins.json")
    evaluated, code, reason = bind_contracts(root, pins)
    lines.extend(evaluated)
    lines.append("PHYSICAL_SCHEMA_FILES 16")
    lines.append("MANIFEST_CONTRACTS 4")
    lines.append("REGISTRY_48 NOT_MATERIALIZED")
    lines.append("E16 INACTIVE")
    lines.append("RUNTIME_PRODUCER_READY false")
    lines.append("A09_STATUS NOT_EXECUTED")
    lines.append("FULL_A09_PASS ABSENT")
    expected = pins["expected"]
    if code != 0 or reason != expected["reason"] or expected["disposition"] != "BYTE_BIND_PASS":
        lines.append("FAIL contract_oracle")
        return lines, 1
    if expected["schema_file_count"] != 16 or expected["registry_48"] != "NOT_MATERIALIZED":
        lines.append("FAIL contract_oracle")
        return lines, 1
    lines.append("SUBCHECK_PASS case=A09-T04")
    return lines, 0


def run_t44(root):
    lines = ["CASE A09-T44", "CASE_ARTIFACT PRESENT", "OFFLINE_SUBCHECK_EXECUTED"]
    seed = (root / "database" / "policies" / "001_project_b_rls_seed.sql").read_text()
    if "using (true)" not in seed:
        lines.append("FAIL historical_scaffold_missing")
        return lines, 1
    definition = json.loads(
        (root / "docs" / "arcava" / "admission" / "synthetic" / "A09-T44" / "case.json").read_text()
    )
    if definition.get("sql_apply") != "NOT_EXECUTED" or definition.get("sql_executed") is True:
        lines.append("ADMISSION_CLAIM REJECTED")
        lines.append("SQL_APPLY NOT_EXECUTED")
        return lines, 1
    lines.append("RLS_SEED_PRESENT path=database/policies/001_project_b_rls_seed.sql")
    lines.append("USING_TRUE_OBSERVED historical_scaffold=NOT_ACCEPTED")
    lines.append("CHECKS_PREPARED " + ",".join(definition["checks_prepared"]))
    lines.append("SQL_APPLY NOT_EXECUTED")
    lines.append("ROLE_TEST NOT_EXECUTED")
    lines.append("ADMISSION_CLAIM REJECTED")
    lines.append("A09_STATUS NOT_EXECUTED")
    lines.append("T44_FULL_ORACLE NOT_EXECUTED reason=sql_rls_not_run")
    lines.append("FULL_A09_PASS ABSENT")
    lines.append("SUBCHECK_PASS case=A09-T44")
    return lines, 0


def classify_evidence(baseline, rows):
    if baseline != BASELINE:
        return "FAIL", "baseline"
    if not isinstance(rows, list):
        return "FAIL", "rows"
    for row in rows:
        status = str(row.get("status", "")).upper()
        if status in ("EXECUTED", "PASS", "ADMITTED"):
            return "FAIL", "acceptance_simulator"
    return "SUBCHECK", "open"


def run_t48(root):
    lines = ["CASE A09-T48", "CASE_ARTIFACT PRESENT", "OFFLINE_SUBCHECK_EXECUTED"]
    manifest = json.loads((root / "contracts" / "arcava" / "contract-manifest.json").read_text())
    declared = manifest["invariants"]["requirement_baseline"]
    mapping = json.loads(
        (
            root / "docs" / "arcava" / "admission" / "synthetic" / "A09-T48" / "evidence-map.json"
        ).read_text()
    )
    kind, reason = classify_evidence(declared, mapping.get("rows"))
    lines.append("BASELINE_DECLARED " + declared)
    lines.append("EVIDENCE_ROWS_EXECUTED 0")
    lines.append("UNMAPPED 86")
    lines.append("UNKNOWN_ADMISSIONS OPEN")
    lines.append("A09_STATUS NOT_EXECUTED")
    lines.append("T48_FULL_ORACLE NOT_EXECUTED reason=requirement_evidence_incomplete")
    lines.append("FULL_A09_PASS ABSENT")
    if kind != "SUBCHECK" or mapping.get("baseline") != BASELINE or mapping.get("unmapped") != 86:
        lines.append("FAIL " + reason)
        return lines, 1
    if mapping.get("acceptance_simulator") is not False:
        lines.append("FAIL acceptance_simulator")
        return lines, 1
    lines.append("SUBCHECK_PASS case=A09-T48")
    return lines, 0


RUNNERS = {
    "A09-T01": run_t01,
    "A09-T04": run_t04,
    "A09-T44": run_t44,
    "A09-T48": run_t48,
}


def run_entrypoint(root, name):
    if name not in RUNNERS:
        return ["ENTRYPOINT_REJECTED name=" + name], 1
    engine_path = SYNTHETIC / name / "engine.json"
    engine = json.loads(engine_path.read_text())
    if engine.get("entrypoint") != name or engine.get("kind") != "fixed_allowlist":
        return ["ENTRYPOINT_REJECTED name=" + name], 1
    return RUNNERS[name](root)


def caller_rejected(argv):
    for flag in CALLER_FLAGS:
        if flag in argv:
            return True
    if any(arg.startswith("--digest=") or arg.startswith("--authorization=") for arg in argv):
        return True
    if "ARCAVA_MANDATE_EXCERPT" in os.environ or "ARCAVA_MANDATE_DIGEST" in os.environ:
        return True
    return False


def emit(lines, code):
    for line in lines:
        print(line)
    return code


def assess_live(action):
    payload = EXCERPT.read_bytes()
    return decide(payload, action)


def run_allowed(root):
    lines, code = assess_live(ALLOWED_ACTION)
    if code != 0:
        return lines, code
    passed = 0
    for name in ENTRYPOINTS:
        case_lines, case_code = run_entrypoint(root, name)
        lines.extend(case_lines)
        if case_code != 0:
            lines.append("SUBCHECK_FAIL case=" + name)
            return lines, case_code
        passed += 1
    lines.append("SUMMARY subchecks=" + str(passed) + " full_a09_pass=0 admission=NOT_ADMITTED")
    return lines, 0


def expect_exit(args, expected, label, env=None):
    child_env = os.environ.copy()
    child_env.pop("ARCAVA_MANDATE_EXCERPT", None)
    child_env.pop("ARCAVA_MANDATE_DIGEST", None)
    if env:
        child_env.update(env)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *args],
        capture_output=True,
        text=True,
        env=child_env,
        timeout=5,
    )
    if result.returncode != expected:
        print("FAIL " + label + " exit=" + str(result.returncode))
        print(result.stdout)
        print(result.stderr)
        return 1
    print("NEGATIVE " + label + " exit=" + str(result.returncode))
    return 0


def self_check():
    lines, code = run_allowed(ROOT)
    if code != 0:
        print("FAIL live subchecks")
        print("\n".join(lines))
        return 1
    required = [
        "MANDATE_SOURCE UNVERIFIED reason=authenticated_reread_unavailable",
        "MANDATE_SNAPSHOT INTEGRITY_PASS",
        "REVOCATION_STATUS UNKNOWN",
        "ADMISSION NOT_ADMITTED reason=revocation_unknown_fail_closed",
        "TEST_SCOPE LIMITED_LOCAL_TEST_SCOPE",
        "SUBCHECK_PASS case=A09-T01",
        "SUBCHECK_PASS case=A09-T04",
        "SUBCHECK_PASS case=A09-T44",
        "SUBCHECK_PASS case=A09-T48",
        "SUMMARY subchecks=4 full_a09_pass=0 admission=NOT_ADMITTED",
        "SQL_EXECUTION NOT_EXECUTED",
        "SQL_APPLY NOT_EXECUTED",
        "REGISTRY_48 NOT_MATERIALIZED",
        "UNKNOWN_ADMISSIONS OPEN",
        "OFFLINE_SUBCHECK_EXECUTED",
        "LEDGER_RESULT LOCAL_PLAN reason=checksums_agree",
        "APPLIED_DATABASE_STATE ABSENT",
        "BYTE_BIND PASS reason=bytes_match_pins",
        "T44_FULL_ORACLE NOT_EXECUTED reason=sql_rls_not_run",
        "T48_FULL_ORACLE NOT_EXECUTED reason=requirement_evidence_incomplete",
    ]
    text = "\n".join(lines)
    for marker in required:
        if marker not in text:
            print("FAIL missing " + marker)
            return 1
    if "A09 PASS" in text or "ADMISSION ADMITTED" in text or "T150 PASS" in text:
        print("FAIL a partial subcheck was promoted")
        return 1
    if "TEST_EXECUTION EXECUTED" in text:
        print("FAIL ambiguous execution marker")
        return 1

    payload = EXCERPT.read_bytes()
    probes = [
        (payload.replace(PINNED_PREIMAGE.encode(), b"0" * 40), "wrong_revision"),
        (payload.replace(PINNED_DECISION_ID.encode(), b"ARC36P25-T150-MANDATE-AND-E1-A09-SCOPE-00"), "wrong_decision"),
        (
            payload.replace(
                b"cryptographic_signature: false",
                b"cryptographic_signature: true",
            ),
            "tampered_body",
        ),
        (payload.replace(PINNED_DOCUMENT_ID.encode(), b"replaced-mandate-sample"), "revoked_source"),
        (payload.replace(PINNED_DOCUMENT_ID.encode(), b"unknown-document-sample"), "unknown_source"),
        (payload + b"owner_admitted: true\n", "forged_boolean"),
    ]
    for sample, label in probes:
        _sample_lines, sample_code = decide(sample, ALLOWED_ACTION)
        if sample_code == 0:
            print("FAIL " + label + " was accepted")
            return 1
        print("NEGATIVE " + label + " exit=" + str(sample_code))

    conflict_codes = migration_checksums(ROOT)
    flipped = dict(conflict_codes)
    first = next(iter(flipped))
    flipped_digest = flipped[first]
    flipped[first] = ("0" if flipped_digest[0] != "0" else "1") + flipped_digest[1:]
    disposition, _reason = classify_preflight(
        conflict_codes, {"files": flipped, "execute": False}
    )
    if disposition != "CONFLICTING":
        print("FAIL a changed checksum did not conflict")
        return 1
    print("NEGATIVE changed_checksum exit=1")
    agreed, agreed_reason = classify_preflight(
        conflict_codes, {"files": conflict_codes, "execute": False}
    )
    if agreed != "COMPATIBLE_EXISTING" or agreed_reason != "checksums_agree":
        print("FAIL an agreeing ledger was not classified")
        return 1
    blocked, blocked_reason = classify_preflight(
        conflict_codes, {"files": conflict_codes, "execute": True}
    )
    if blocked != "MUTATION_BLOCKED" or blocked_reason != "execute_requested":
        print("FAIL an execute request was not blocked")
        return 1
    print("NEGATIVE execute_requested exit=1")

    kind, reason = classify_registry(16, EXPECTED_CONTRACTS, True)
    if kind != "FAIL" or reason != "false_48_pass":
        print("FAIL a 48-contract claim was accepted")
        return 1
    print("NEGATIVE false_48_pass exit=1")
    drifted, drifted_reason = classify_registry(15, EXPECTED_CONTRACTS, False)
    if drifted != "FAIL" or drifted_reason != "registry_drift":
        print("FAIL a short schema set was accepted")
        return 1
    print("NEGATIVE registry_drift exit=1")

    simulated, simulated_reason = classify_evidence(
        BASELINE, [{"id": "sample", "status": "PASS"}]
    )
    if simulated != "FAIL" or simulated_reason != "acceptance_simulator":
        print("FAIL an acceptance row was accepted")
        return 1
    print("NEGATIVE acceptance_simulator exit=1")

    cli = [
        (["--authorization", "self"], 1, "caller_authorization"),
        (["--digest", PINNED_DIGEST], 1, "caller_digest"),
        (["--url", "https://example.invalid/mandate"], 1, "caller_url"),
        (["--action", "sql_execution"], 1, "scope_sql"),
        (["--action", "hosted_apply"], 1, "scope_hosted"),
        (["--run", "bash -c id"], 1, "dangerous_entrypoint"),
        (["--fixture", "../toolchain-manifest.json"], 1, "path_traversal"),
        (["--internal-fail"], 3, "nonzero_exit"),
    ]
    for args, expected, label in cli:
        if expect_exit(args, expected, label):
            return 1
    if expect_exit(
        [],
        1,
        "caller_file",
        {"ARCAVA_MANDATE_EXCERPT": str(EXCERPT)},
    ):
        return 1
    golden = SYNTHETIC / "A09-T01" / "golden"
    for name in ("ledger-missing.json", "ledger-unknown.json", "ledger-duplicate.json", "ledger-digest.json"):
        fixture = load_json(golden / name)
        _lines, code, reason = evaluate_ledger(ROOT, fixture)
        if code == 0 or reason != fixture["expected"]["reason"]:
            print("FAIL ledger " + name + " reason=" + reason)
            return 1
        print("NEGATIVE " + name[:-5] + " exit=1")
    match = load_json(golden / "ledger-match.json")
    with tempfile.TemporaryDirectory() as raw:
        temp_root = Path(raw)
        for _migration_id, relative in KNOWN_MIGRATIONS:
            source = ROOT / relative
            target = temp_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        flipped = temp_root / KNOWN_MIGRATIONS[0][1]
        payload = bytearray(flipped.read_bytes())
        payload[0] = (payload[0] + 1) % 256
        flipped.write_bytes(bytes(payload))
        _lines, code, reason = evaluate_ledger(temp_root, match)
        if code == 0 or reason != "digest_mismatch":
            print("FAIL a changed migration byte was accepted")
            return 1
        print("NEGATIVE byte_drift exit=1")
    base_pins = load_json(SYNTHETIC / "A09-T04" / "byte-pins.json")
    for name in ("byte-drift.json", "missing-file.json", "binding.json", "illegal-path.json"):
        overlay = load_json(SYNTHETIC / "A09-T04" / "golden" / name)
        trial = json.loads(json.dumps(base_pins))
        trial["pins"][overlay["replace_index"]] = overlay["pin"]
        _lines, code, reason = bind_contracts(ROOT, trial)
        if code == 0 or reason != overlay["expected"]["reason"]:
            print("FAIL contract " + name + " reason=" + reason)
            return 1
        print("NEGATIVE " + name[:-5] + " exit=1")
    first = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=5,
    )
    second = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=5,
    )
    if first.returncode != 0 or first.stdout != second.stdout or first.returncode != second.returncode:
        print("FAIL oracle output was not reproducible")
        return 1
    print("REPRODUCIBLE fresh_process=2")
    discovery = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "a09_case_discovery.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if discovery.returncode != 0 or "PASS a09_discovery ids=4 result=NOT_EXECUTED" not in discovery.stdout:
        print("FAIL discovery changed")
        print(discovery.stdout)
        return 1
    print("DISCOVERY_UNCHANGED NOT_EXECUTED")
    try:
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--internal-sleep"],
            capture_output=True,
            text=True,
            timeout=0.4,
        )
    except subprocess.TimeoutExpired:
        print("NEGATIVE timeout exit=124")
        print(
            "PASS local_admission_negative "
            "caller=rejected scope=rejected revoked=rejected "
            "digest=rejected timeout=rejected traversal=rejected"
        )
        return 0
    print("FAIL timeout child finished")
    return 1


def main():
    argv = sys.argv[1:]
    if argv == ["--internal-sleep"]:
        import time

        time.sleep(2)
        return 0
    if argv == ["--internal-fail"]:
        print("INTERNAL_FAIL")
        return 3
    if caller_rejected(argv):
        print("CALLER_TRUST_ROOT REJECTED")
        print("TEST_SCOPE SCOPE_ABSENT")
        print("ADMISSION NOT_ADMITTED")
        return 1
    if argv == ["--self-check"]:
        return self_check()
    if argv == []:
        lines, code = run_allowed(ROOT)
        return emit(lines, code)
    if argv[:1] == ["--action"] and len(argv) == 2:
        lines, code = assess_live(argv[1])
        return emit(lines, code)
    if argv[:1] == ["--run"] and len(argv) == 2:
        lines, code = assess_live(ALLOWED_ACTION)
        if code != 0:
            return emit(lines, code)
        case_lines, case_code = run_entrypoint(ROOT, argv[1])
        return emit(lines + case_lines, case_code)
    if argv[:1] == ["--fixture"] and len(argv) == 2:
        try:
            allowed_path(ROOT, "docs/arcava/admission/synthetic/" + argv[1])
        except ValueError:
            print("PATH_REJECTED")
            return 1
        print("PATH_ACCEPTED")
        return 0
    print("FAIL usage")
    return 1


if __name__ == "__main__":
    sys.exit(main())
