#!/usr/bin/env python3
"""Check captured loopback producer requests against the offline request schemas.

A schema-valid request is not a PIAC grant, a KDB right, or a runtime producer admission.
"""

import importlib.metadata
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

from validate_arcava_producer_wire_fixtures import load_schemas, ref_error

ROOT = Path(__file__).resolve().parents[1]
WIRED = ("CT-ARC-002", "CT-ARC-003", "CT-ARC-004")
MINIMUMS = {
    ("CT-ARC-002", "OK"): 2,
    ("CT-ARC-002", "WITHDRAWN"): 1,
    ("CT-ARC-002", "NOT_FOUND"): 1,
    ("CT-ARC-003", "OK"): 1,
    ("CT-ARC-003", "DENIED"): 1,
    ("CT-ARC-004", "OK"): 2,
    ("CT-ARC-004", "STALE"): 1,
    ("CT-ARC-004", "NOT_FOUND"): 1,
}


def fail(message):
    return message


def walk(node, visit):
    if isinstance(node, dict):
        visit(node)
        for value in node.values():
            walk(value, visit)
    elif isinstance(node, list):
        for value in node:
            walk(value, visit)


def claim_error(document):
    blob = json.dumps(document, separators=(",", ":"))
    if "T050 PASS" in blob or "A09 PASS" in blob or document.get("runtime_producer_ready") is True:
        return "runtime admission rejected"
    if document.get("piac_grant") == "trusted" or document.get("kdb_rights") == "granted":
        return "untrusted claim rejected"
    found = []

    def visit(item):
        if item.get("rights_state") == "granted" or item.get("verified") is True:
            found.append("untrusted claim rejected")

    walk(document, visit)
    return found[0] if found else None


def alias_error(node):
    if isinstance(node, dict):
        for value in node.values():
            if alias_error(value):
                return True
    elif isinstance(node, list):
        for value in node:
            if alias_error(value):
                return True
    return node == "latest"


def schema_label(error):
    message = error.message
    if "is a required property" in message:
        return "required field missing"
    if message.startswith("Additional properties are not allowed") or message.startswith("Unevaluated properties are not allowed"):
        return "extra property rejected"
    return "schema instance rejected " + error.json_path


def check_request(contract, document, documents, registry):
    if contract == "CT-ARC-R03-REM-001":
        return fail("reminder contract not tested")
    if contract not in WIRED:
        return fail("contract id rejected")
    if not isinstance(document, dict):
        return fail("schema instance rejected $")
    if document.get("contract_id") != contract:
        return fail("route contract rejected")
    if document.get("schema_version") != "1.0":
        return fail("version rejected")
    if alias_error(document):
        return fail("alias rejected")
    marker = claim_error(document)
    if marker:
        return marker
    schema = documents["urn:arcava:{0}:1.0:request".format(contract)]
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    if errors:
        return fail(schema_label(errors[0]))
    return None


def consent_untrusted(document):
    ref = document.get("consent_decision_ref")
    return isinstance(ref, dict) and ref.get("producer_namespace") == "PIAC"


def validate(root, requests_path):
    documents, registry, error = load_schemas(root)
    if error:
        return error, {}
    counts = {}
    checked = 0
    excluded = 0
    untrusted = 0
    for raw in Path(requests_path).read_text().splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t", 3)
        if len(parts) != 4:
            return fail("capture row rejected"), {}
        contract, status_text, outcome, body = parts
        try:
            status = int(status_text)
            document = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            return fail("capture row rejected"), {}
        if status == 401:
            excluded += 1
            continue
        error = check_request(contract, document, documents, registry)
        if error:
            return error, {}
        counts[(contract, outcome)] = counts.get((contract, outcome), 0) + 1
        if consent_untrusted(document):
            untrusted += 1
        checked += 1
    if checked == 0 and excluded:
        return fail("unauthorized outside envelope"), {}
    for key, minimum in MINIMUMS.items():
        if counts.get(key, 0) < minimum:
            return fail("mandatory case missing " + key[0] + " " + key[1]), {}
    if untrusted < 1:
        return fail("untrusted consent ref missing"), {}
    return None, {"checked": checked, "excluded": excluded, "untrusted": untrusted, "counts": counts}


def report(summary):
    print("REQUEST_CHECKED count={0} excluded_401={1}".format(summary["checked"], summary["excluded"]))
    for key in MINIMUMS:
        print("REQUEST_CASE {0} {1} count={2}".format(key[0], key[1], summary["counts"].get(key, 0)))
    print("CONSENT_REF untrusted count={0} authority=not_a_grant".format(summary["untrusted"]))
    print("UNAUTHORIZED_401 count={0} rationale=outside_the_producer_envelope".format(summary["excluded"]))
    print("RUNTIME_PRODUCER_NOT_ADMITTED")
    print("R03_NOT_TESTED")
    print("ENVELOPES_NOT_EXECUTED count=3")
    print("HOSTED_DB UNKNOWN")
    print("TOOL python={0} jsonschema={1}".format(
        ".".join(str(part) for part in sys.version_info[:3]),
        importlib.metadata.version("jsonschema"),
    ))
    print("PASS arcava_producer_request_wire mandatory=satisfied")


def write_rows(path, rows):
    lines = []
    for contract, status, outcome, body in rows:
        payload = body if isinstance(body, str) else json.dumps(body)
        lines.append(contract + "\t" + str(status) + "\t" + outcome + "\t" + payload)
    path.write_text("\n".join(lines))


def run_file(path):
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--requests", str(path)],
        capture_output=True,
        text=True,
    )


def expect_fail(rows, label):
    temp = Path(tempfile.mkdtemp())
    target = temp / "requests.ndjson"
    write_rows(target, rows)
    result = run_file(target)
    if result.returncode == 0 or result.stdout.strip() != "FAIL " + label:
        print("FAIL negative " + label)
        print(result.stdout)
        print(result.stderr)
        return 1
    if "T050 PASS" in result.stdout or "A09 PASS" in result.stdout:
        print("FAIL negative printed an admission")
        return 1
    print("PASS negative " + label.split(":", 1)[0])
    return 0


def self_check(requests_path):
    good = run_file(requests_path)
    if good.returncode != 0 or "PASS arcava_producer_request_wire mandatory=satisfied" not in good.stdout:
        print("FAIL live requests")
        print(good.stdout)
        print(good.stderr)
        return 1
    if "CONSENT_REF untrusted" not in good.stdout or "authority=not_a_grant" not in good.stdout:
        print("FAIL live requests consent line")
        return 1
    if "UNAUTHORIZED_401 count=0" not in good.stdout:
        print("FAIL live requests 401 line")
        return 1
    if "T050 PASS" in good.stdout or "A09 PASS" in good.stdout:
        print("FAIL live requests admission line")
        return 1
    print("PASS live_requests")
    sample = None
    for raw in Path(requests_path).read_text().splitlines():
        contract, status_text, outcome, body = raw.split("\t", 3)
        if contract == "CT-ARC-002" and outcome == "OK":
            sample = (contract, int(status_text), outcome, json.loads(body))
            break
    if sample is None:
        print("FAIL live requests have no 002 row")
        return 1
    contract, status, outcome, document = sample
    missing = json.loads(json.dumps(document))
    missing.pop("correlation_id", None)
    wrong_id = json.loads(json.dumps(document))
    wrong_id["contract_id"] = "CT-ARC-003"
    wrong_version = json.loads(json.dumps(document))
    wrong_version["schema_version"] = "9.9"
    latest = json.loads(json.dumps(document))
    latest["projection_or_resource"]["journey_id"] = "latest"
    extra = json.loads(json.dumps(document))
    extra["admin"] = True
    claimed = json.loads(json.dumps(document))
    claimed["piac_grant"] = "trusted"
    cases = [
        ([(contract, status, outcome, missing)], "required field missing"),
        ([(contract, status, outcome, wrong_id)], "route contract rejected"),
        ([(contract, status, outcome, wrong_version)], "version rejected"),
        ([(contract, status, outcome, latest)], "alias rejected"),
        ([(contract, status, outcome, extra)], "extra property rejected"),
        ([(contract, status, outcome, claimed)], "untrusted claim rejected"),
        ([("CT-ARC-002", status, outcome, "{not json")], "capture row rejected"),
        ([("CT-ARC-999", status, outcome, document)], "contract id rejected"),
        ([("CT-ARC-002", 401, "UNAUTHORIZED", {"contract_id": "CT-ARC-002"})], "unauthorized outside envelope"),
        ([], "mandatory case missing CT-ARC-002 OK"),
    ]
    for rows, label in cases:
        if expect_fail(rows, label):
            return 1
    documents, _registry, error = load_schemas(ROOT)
    if error:
        print("FAIL " + error)
        return 1
    for ref in (
        "urn:arcava:types:1.0:QueryEnvelope#/$defs/NO_SUCH",
        "https://example.invalid/schema",
    ):
        seen = ref_error(ref, documents)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--reject-ref", ref],
            capture_output=True,
            text=True,
        )
        if seen != "schema ref not verified: " + ref or result.returncode == 0 or result.stdout.strip() != "FAIL " + seen:
            print("FAIL negative schema ref not verified")
            print(result.stdout)
            return 1
    print("PASS negative schema ref not verified")
    print("PASS arcava_producer_request_wire_negative")
    return 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--reject-ref":
        documents, _registry, error = load_schemas(ROOT)
        if error:
            print("FAIL " + error)
            return 1
        ref = ref_error(sys.argv[2], documents)
        print("FAIL " + (ref or "schema ref verified"))
        return 1
    requests_path = None
    check = False
    args = sys.argv[1:]
    while args:
        item = args.pop(0)
        if item == "--self-check":
            check = True
        elif item == "--requests" and args:
            requests_path = Path(args.pop(0))
        else:
            print("usage: validate_arcava_producer_request_wire.py --requests PATH [--self-check]", file=sys.stderr)
            return 2
    if requests_path is None:
        print("usage: validate_arcava_producer_request_wire.py --requests PATH [--self-check]", file=sys.stderr)
        return 2
    if check:
        return self_check(requests_path)
    error, summary = validate(ROOT, requests_path)
    if error:
        print("FAIL " + error)
        return 1
    report(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
