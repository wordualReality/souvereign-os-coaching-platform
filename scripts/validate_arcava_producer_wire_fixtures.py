#!/usr/bin/env python3
"""Check captured loopback producer bodies against the offline Arcava schemas.

A passing run is schema conformance of synthetic fixtures. It does not admit a runtime producer.
"""

import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_RELATIVE = "contracts/arcava/contract-manifest.json"
WIRED = ("CT-ARC-002", "CT-ARC-003", "CT-ARC-004")
OUTCOMES = {
    "CT-ARC-002": {"OK", "NOT_FOUND", "STALE", "WITHDRAWN", "REVALIDATION_REQUIRED"},
    "CT-ARC-003": {"OK", "DENIED", "STALE", "PRECONDITION_FAILED"},
    "CT-ARC-004": {"OK", "NOT_FOUND", "STALE"},
}
STATUS_FOR = {
    "OK": 200,
    "NOT_FOUND": 404,
    "DENIED": 403,
    "WITHDRAWN": 422,
    "STALE": 409,
    "REVALIDATION_REQUIRED": 422,
}
MINIMUMS = {
    ("CT-ARC-002", "OK", ""): 2,
    ("CT-ARC-002", "WITHDRAWN", ""): 1,
    ("CT-ARC-002", "NOT_FOUND", ""): 1,
    ("CT-ARC-003", "OK", "ALLOW"): 2,
    ("CT-ARC-003", "OK", "DENY"): 1,
    ("CT-ARC-003", "DENIED", ""): 1,
    ("CT-ARC-004", "OK", ""): 2,
    ("CT-ARC-004", "STALE", ""): 1,
    ("CT-ARC-004", "NOT_FOUND", ""): 1,
}


def fail(message):
    return message


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def bounded(root, declared):
    if not isinstance(declared, str) or declared.startswith(("/", "\\")) or "\\" in declared:
        return None
    parts = Path(declared).parts
    if ".." in parts or parts[:2] != ("contracts", "arcava"):
        return None
    base = (root / "contracts" / "arcava").resolve()
    candidate = (root / declared).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None
    return candidate


def pointer_exists(document, pointer):
    if pointer in ("", "#"):
        return True
    if not pointer.startswith("#/"):
        return False
    node = document
    for raw in pointer[2:].split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return False
    return True


def collect_refs(node, found):
    if isinstance(node, dict):
        if isinstance(node.get("$ref"), str):
            found.append(node["$ref"])
        for value in node.values():
            collect_refs(value, found)
    elif isinstance(node, list):
        for value in node:
            collect_refs(value, found)


def ref_error(ref, documents):
    if ref.startswith(("http://", "https://")):
        return "schema ref not verified: " + ref
    base, _, fragment = ref.partition("#")
    if base not in documents:
        return "schema ref not verified: " + ref
    if fragment and not pointer_exists(documents[base], "#" + fragment):
        return "schema ref not verified: " + ref
    return None


def load_schemas(root):
    manifest_path = root / MANIFEST_RELATIVE
    manifest = json.loads(manifest_path.read_text())
    documents = {}
    entries = list(manifest["common_components"])
    for contract in manifest["contracts"]:
        entries.extend(contract["physical_schemas"])
    for entry in entries:
        path = bounded(root, entry["path"])
        if path is None or not path.is_file():
            return None, None, fail("schema file missing")
        payload = path.read_bytes()
        if sha256(payload) != entry["sha256"]:
            return None, None, fail("digest mismatch")
        document = json.loads(payload.decode("utf-8"))
        documents[document["$id"]] = document
    refs = []
    for document in documents.values():
        collect_refs(document, refs)
    for ref in refs:
        error = ref_error(ref, documents)
        if error:
            return None, None, fail(error)
    registry = Registry().with_resources(
        [(schema_id, Resource.from_contents(document)) for schema_id, document in documents.items()]
    )
    return documents, registry, None


def walk(node, visit):
    if isinstance(node, dict):
        visit(node)
        for value in node.values():
            walk(value, visit)
    elif isinstance(node, list):
        for value in node:
            walk(value, visit)


def admission_error(document):
    blob = json.dumps(document, separators=(",", ":"))
    if "T050 PASS" in blob or "A09 PASS" in blob or document.get("runtime_producer_ready") is True:
        return "runtime admission rejected"
    found = []

    def visit(item):
        rights = item.get("rights_state")
        if isinstance(rights, str) and rights != "caller-supplied-not-verified":
            found.append("kdb rights rejected")
        if item.get("producer_namespace") == "PIAC":
            found.append("piac grant rejected")
        refs = item.get("runtime_session_refs")
        if isinstance(refs, list) and refs:
            found.append("sov session rejected")

    walk(document, visit)
    return found[0] if found else None


def decision_of(document):
    payload = document.get("payload")
    if not isinstance(payload, dict):
        return ""
    access = payload.get("effective_access")
    if not isinstance(access, dict):
        return ""
    decision = access.get("decision")
    return decision if decision in ("ALLOW", "DENY") else ""


def schema_label(error):
    message = error.message
    if "is a required property" in message:
        return "required field missing"
    if message.startswith("Additional properties are not allowed"):
        return "extra property rejected"
    if "is not one of" in message or message.startswith("None is not of type"):
        return "enum rejected"
    return "schema instance rejected " + error.json_path


def check_row(contract, status, document, documents, registry):
    if contract == "CT-ARC-R03-REM-001":
        return fail("reminder contract not tested")
    if contract not in WIRED:
        return fail("contract id rejected")
    if not isinstance(document, dict):
        return fail("schema instance rejected $")
    if document.get("contract_id") != contract:
        return fail("contract id rejected")
    if document.get("schema_version") != "1.0":
        return fail("version rejected")
    outcome = document.get("outcome")
    if outcome not in OUTCOMES[contract]:
        return fail("outcome rejected")
    if status != STATUS_FOR[outcome]:
        return fail("status rejected")
    marker = admission_error(document)
    if marker:
        return marker
    kind = "result" if outcome == "OK" else "error"
    schema = documents["urn:arcava:{0}:1.0:{1}".format(contract, kind)]
    validator = Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    if errors:
        return fail(schema_label(errors[0]))
    return None


def case_key(contract, document):
    outcome = document["outcome"]
    decision = decision_of(document) if contract == "CT-ARC-003" and outcome == "OK" else ""
    return contract, outcome, decision


def validate(root, bodies_path):
    documents, registry, error = load_schemas(root)
    if error:
        return error, {}
    rows = Path(bodies_path).read_text().splitlines()
    counts = {}
    checked = 0
    excluded = 0
    for raw in rows:
        if not raw.strip():
            continue
        parts = raw.split("\t", 2)
        if len(parts) != 3:
            return fail("capture row rejected"), {}
        contract, status_text, body = parts
        try:
            status = int(status_text)
            document = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            return fail("capture row rejected"), {}
        if status == 401:
            excluded += 1
            continue
        error = check_row(contract, status, document, documents, registry)
        if error:
            return error, {}
        key = case_key(contract, document)
        counts[key] = counts.get(key, 0) + 1
        checked += 1
    if checked == 0 and excluded:
        return fail("unauthorized outside envelope"), counts
    for key, minimum in MINIMUMS.items():
        if counts.get(key, 0) < minimum:
            label = " ".join(part for part in key if part)
            return fail("mandatory case missing " + label), counts
    return None, {"checked": checked, "excluded": excluded, "counts": counts}


def report(summary):
    print("WIRE_CHECKED count={0} excluded_401={1}".format(summary["checked"], summary["excluded"]))
    for key in MINIMUMS:
        label = " ".join(part for part in key if part)
        print("WIRE_CASE {0} count={1}".format(label, summary["counts"].get(key, 0)))
    print("UNAUTHORIZED_EXCLUDED rationale=status_401_is_outside_the_producer_envelope")
    print("REPLAY_AND_RESTART_ROWS checked")
    print("RUNTIME_PRODUCER_NOT_ADMITTED")
    print("R03_NOT_TESTED")
    print("ENVELOPES_NOT_EXECUTED count=3")
    print("HOSTED_DB UNKNOWN")
    print("TOOL python={0} jsonschema={1}".format(
        ".".join(str(part) for part in sys.version_info[:3]),
        importlib.metadata.version("jsonschema"),
    ))
    print("PASS arcava_producer_wire mandatory=satisfied")


def write_rows(path, rows):
    path.write_text("\n".join(contract + "\t" + str(status) + "\t" + json.dumps(body) for contract, status, body in rows))


def run_file(path):
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--bodies", str(path)],
        capture_output=True,
        text=True,
    )


def expect_fail(rows, label):
    temp = Path(tempfile.mkdtemp())
    target = temp / "bodies.ndjson"
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


def self_check(bodies_path):
    good = run_file(bodies_path)
    if good.returncode != 0 or "PASS arcava_producer_wire mandatory=satisfied" not in good.stdout:
        print("FAIL live capture")
        print(good.stdout)
        print(good.stderr)
        return 1
    if "RUNTIME_PRODUCER_NOT_ADMITTED" not in good.stdout or "R03_NOT_TESTED" not in good.stdout:
        print("FAIL live capture status")
        return 1
    if "T050 PASS" in good.stdout or "A09 PASS" in good.stdout:
        print("FAIL live capture admission line")
        return 1
    print("PASS live_capture")
    sample = None
    access = None
    for raw in Path(bodies_path).read_text().splitlines():
        contract, status_text, body = raw.split("\t", 2)
        document = json.loads(body)
        if sample is None and contract == "CT-ARC-002" and document.get("outcome") == "OK":
            sample = (contract, int(status_text), document)
        if access is None and contract == "CT-ARC-003" and document.get("outcome") == "OK":
            access = (contract, int(status_text), document)
    if sample is None or access is None:
        print("FAIL live capture has no result row")
        return 1
    contract, status, document = sample
    missing = json.loads(json.dumps(document))
    missing.pop("correlation_id", None)
    mutated = json.loads(json.dumps(document))
    mutated["outcome"] = "MAYBE"
    wrong_id = json.loads(json.dumps(document))
    wrong_id["contract_id"] = "CT-ARC-999"
    wrong_version = json.loads(json.dumps(document))
    wrong_version["schema_version"] = "9.9"
    extra = json.loads(json.dumps(document))
    extra["admin"] = True
    admitted = json.loads(json.dumps(document))
    admitted["runtime_producer_ready"] = True
    granted = json.loads(json.dumps(document))
    granted["payload"]["phases"][0]["steps"][0]["canonical_bindings"][0]["rights_state"] = "granted"
    denied_status = (contract, 500, document)
    access_contract, access_status, access_body = access
    enum_body = json.loads(json.dumps(access_body))
    enum_body["payload"]["effective_access"]["decision"] = "GRANTED"
    piac = json.loads(json.dumps(access_body))
    piac["payload"]["enrollment_ref"]["producer_namespace"] = "PIAC"
    cases = [
        ([(contract, status, missing)], "required field missing"),
        ([(contract, status, mutated)], "outcome rejected"),
        ([(contract, status, wrong_id)], "contract id rejected"),
        ([(contract, status, wrong_version)], "version rejected"),
        ([(contract, status, extra)], "extra property rejected"),
        ([(contract, status, admitted)], "runtime admission rejected"),
        ([(access_contract, access_status, enum_body)], "enum rejected"),
        ([(contract, status, granted)], "kdb rights rejected"),
        ([(access_contract, access_status, piac)], "piac grant rejected"),
        ([denied_status], "status rejected"),
        ([("CT-ARC-002", 401, {"contract_id": "CT-ARC-002", "outcome": "OK"})], "unauthorized outside envelope"),
        ([], "mandatory case missing CT-ARC-002 OK"),
    ]
    for rows, label in cases:
        if expect_fail(rows, label):
            return 1
    documents, registry, error = load_schemas(ROOT)
    if error:
        print("FAIL " + error)
        return 1
    fragment = ref_error("urn:arcava:types:1.0:QueryEnvelope#/$defs/NO_SUCH", documents)
    remote = ref_error("https://example.invalid/schema", documents)
    if fragment != "schema ref not verified: urn:arcava:types:1.0:QueryEnvelope#/$defs/NO_SUCH":
        print("FAIL unresolved fragment")
        return 1
    if remote != "schema ref not verified: https://example.invalid/schema":
        print("FAIL external ref")
        return 1
    for ref in (
        "urn:arcava:types:1.0:QueryEnvelope#/$defs/NO_SUCH",
        "https://example.invalid/schema",
    ):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--reject-ref", ref],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or result.stdout.strip() != "FAIL schema ref not verified: " + ref:
            print("FAIL negative schema ref not verified")
            print(result.stdout)
            return 1
    print("PASS negative schema ref not verified")
    print("PASS arcava_producer_wire_negative")
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
    bodies = None
    check = False
    args = sys.argv[1:]
    while args:
        item = args.pop(0)
        if item == "--self-check":
            check = True
        elif item == "--bodies" and args:
            bodies = Path(args.pop(0))
        else:
            print("usage: validate_arcava_producer_wire_fixtures.py --bodies PATH [--self-check]", file=sys.stderr)
            return 2
    if bodies is None:
        print("usage: validate_arcava_producer_wire_fixtures.py --bodies PATH [--self-check]", file=sys.stderr)
        return 2
    if check:
        return self_check(bodies)
    error, summary = validate(ROOT, bodies)
    if error:
        print("FAIL " + error)
        return 1
    report(summary)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValidationError as exc:
        print("FAIL schema instance rejected " + exc.json_path)
        sys.exit(1)
