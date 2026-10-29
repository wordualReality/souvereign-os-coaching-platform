#!/usr/bin/env python3
"""Check the offline Arcava contract manifest. This does not admit a runtime producer."""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema.exceptions import SchemaError
from jsonschema.validators import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_RELATIVE = "contracts/arcava/contract-manifest.json"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
PHYSICAL_STATUS = "MATERIALIZED_OFFLINE_CANONICAL_RUNTIME_PENDING"
FROZEN = {
    "CT-ARC-002": {"edges": ("E08",), "kinds": ("request", "result", "error")},
    "CT-ARC-003": {"edges": ("E09",), "kinds": ("request", "result", "error")},
    "CT-ARC-004": {"edges": ("E08",), "kinds": ("request", "result", "error")},
    "CT-ARC-R03-REM-001": {"edges": ("E10",), "kinds": ("request", "result", "event", "error")},
}
COMMON_PATHS = (
    "contracts/arcava/types/1.0/QueryEnvelope.schema.json",
    "contracts/arcava/types/1.0/ResponseEnvelope.schema.json",
    "contracts/arcava/types/1.0/EventEnvelope.schema.json",
)
ROOT_KEYS = {
    "manifest_version",
    "producer",
    "semantic_registry",
    "common_components",
    "contracts",
    "source_refs",
    "invariants",
}
CONTRACT_KEYS = {
    "contract_id",
    "producer",
    "status",
    "aliases",
    "profile_version",
    "consumer_edges",
    "physical_schemas",
    "outcomes",
    "compatibility",
    "physical_status",
    "runtime_producer_ready",
    "runtime_backing",
    "source_refs",
}


def fail(message):
    return message


def keys_ok(value, allowed):
    return isinstance(value, dict) and set(value) == allowed


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def bounded_file(root, declared):
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


def source_refs_ok(items):
    if not isinstance(items, list) or not items:
        return False
    for item in items:
        if not keys_ok(item, {"document_id", "revision_id", "role"}):
            return False
        if not all(isinstance(item[key], str) and item[key] for key in item):
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


def check_document(root, declared, digest, expected_id, seen_paths, known_ids):
    if declared in seen_paths:
        return fail("duplicate path")
    seen_paths.add(declared)
    document_path = bounded_file(root, declared)
    if document_path is None:
        return fail("path escape")
    if not document_path.is_file():
        return fail("schema file missing")
    payload = document_path.read_bytes()
    if sha256(payload) != digest:
        return fail("digest mismatch")
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return fail("schema json rejected")
    if not isinstance(document, dict):
        return fail("schema draft rejected")
    if document.get("$schema") != DRAFT:
        return fail("schema draft rejected")
    if "$id" not in document:
        return fail("schema id missing")
    if document.get("$id") != expected_id:
        return fail("schema id mismatch")
    try:
        Draft202012Validator.check_schema(document)
    except SchemaError:
        return fail("schema draft rejected")
    known_ids.append((expected_id, document))
    return None


def unresolved_ref(ref, known_ids):
    if ref.startswith(("http://", "https://")):
        return ref
    base = ref.split("#", 1)[0]
    if base and base not in known_ids:
        return ref
    return None


def validate(root):
    manifest_path = root / MANIFEST_RELATIVE
    if not manifest_path.is_file():
        return fail("manifest shape rejected")
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return fail("manifest shape rejected")
    if not keys_ok(manifest, ROOT_KEYS):
        return fail("manifest shape rejected")
    if manifest["producer"] != "ARCAVA":
        return fail("producer rejected")
    if manifest["manifest_version"] != "1.0":
        return fail("version rejected")
    if manifest["semantic_registry"] != MANIFEST_RELATIVE:
        return fail("manifest shape rejected")
    if not source_refs_ok(manifest["source_refs"]):
        return fail("manifest shape rejected")
    invariants = manifest["invariants"]
    if not keys_ok(
        invariants,
        {"requirement_baseline", "food_scan_dosha_ai", "runtime_readiness_not_inferred_from_schema_presence"},
    ):
        return fail("manifest shape rejected")
    if invariants["runtime_readiness_not_inferred_from_schema_presence"] is not True:
        return fail("runtime producer admission rejected")
    if not isinstance(manifest["common_components"], list) or not isinstance(manifest["contracts"], list):
        return fail("manifest shape rejected")

    seen_paths = set()
    known = []
    common_paths = []
    for entry in manifest["common_components"]:
        if not keys_ok(entry, {"path", "sha256"}):
            return fail("manifest shape rejected")
        name = Path(entry["path"]).name.replace(".schema.json", "")
        error = check_document(
            root,
            entry["path"],
            entry["sha256"],
            "urn:arcava:types:1.0:" + name,
            seen_paths,
            known,
        )
        if error:
            return error
        common_paths.append(entry["path"])
    if tuple(sorted(common_paths)) != tuple(sorted(COMMON_PATHS)) or len(common_paths) != len(COMMON_PATHS):
        return fail("common component rejected")

    seen_ids = []
    for contract in manifest["contracts"]:
        if not keys_ok(contract, CONTRACT_KEYS):
            return fail("manifest shape rejected")
        contract_id = contract["contract_id"]
        if contract_id not in FROZEN:
            return fail("contract id rejected")
        frozen = FROZEN[contract_id]
        if contract["producer"] != "ARCAVA":
            return fail("producer rejected")
        if contract["aliases"] != []:
            return fail("alias rejected")
        if contract["status"] != "ACTIVE":
            return fail("manifest shape rejected")
        if contract["profile_version"] != "1.0":
            return fail("version rejected")
        if tuple(contract["consumer_edges"]) != frozen["edges"]:
            return fail("consumer edge rejected")
        compatibility = contract["compatibility"]
        if not keys_ok(compatibility, {"major", "minor", "unversioned_fallback"}):
            return fail("manifest shape rejected")
        if compatibility["unversioned_fallback"] is not False:
            return fail("unversioned fallback rejected")
        if compatibility["major"] != 1 or compatibility["minor"] != 0:
            return fail("version rejected")
        if contract["physical_status"] != PHYSICAL_STATUS:
            return fail("physical status rejected")
        if contract["runtime_producer_ready"] is not False:
            return fail("runtime producer admission rejected")
        if not isinstance(contract["runtime_backing"], str) or not contract["runtime_backing"]:
            return fail("manifest shape rejected")
        if not isinstance(contract["outcomes"], list) or not contract["outcomes"]:
            return fail("manifest shape rejected")
        if not all(isinstance(item, str) and item for item in contract["outcomes"]):
            return fail("manifest shape rejected")
        if not source_refs_ok(contract["source_refs"]):
            return fail("manifest shape rejected")
        if not isinstance(contract["physical_schemas"], list):
            return fail("manifest shape rejected")
        kinds = []
        for schema in contract["physical_schemas"]:
            if not keys_ok(schema, {"kind", "path", "sha256"}):
                return fail("manifest shape rejected")
            kind = schema["kind"]
            if kind not in frozen["kinds"]:
                return fail("schema kind rejected")
            if bounded_file(root, schema["path"]) is None:
                return fail("path escape")
            expected_path = "contracts/arcava/{0}/1.0/{1}.schema.json".format(contract_id, kind)
            if schema["path"] != expected_path:
                return fail("schema id mismatch")
            error = check_document(
                root,
                schema["path"],
                schema["sha256"],
                "urn:arcava:{0}:1.0:{1}".format(contract_id, kind),
                seen_paths,
                known,
            )
            if error:
                return error
            kinds.append(kind)
        if tuple(sorted(kinds)) != tuple(sorted(frozen["kinds"])) or len(kinds) != len(set(kinds)):
            return fail("schema kind rejected")
        seen_ids.append(contract_id)
    if tuple(sorted(seen_ids)) != tuple(sorted(FROZEN)) or len(seen_ids) != len(FROZEN):
        return fail("contract id missing")

    known_ids = {item[0] for item in known}
    for schema_id, document in known:
        found = []
        collect_refs(document, found)
        for ref in found:
            missing = unresolved_ref(ref, known_ids)
            if missing:
                return fail("schema ref not verified: " + missing)
    if len(seen_paths) != 16:
        return fail("manifest shape rejected")
    return None


def mutate_copy():
    temp = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "contracts" / "arcava", temp / "contracts" / "arcava")
    return temp


def manifest_of(root):
    path = root / MANIFEST_RELATIVE
    return path, json.loads(path.read_text())


def save_manifest(path, payload):
    path.write_text(json.dumps(payload))


def retarget_digest(root, relative):
    path, payload = manifest_of(root)
    digest = sha256((root / relative).read_bytes())
    for entry in payload["common_components"]:
        if entry["path"] == relative:
            entry["sha256"] = digest
    for contract in payload["contracts"]:
        for schema in contract["physical_schemas"]:
            if schema["path"] == relative:
                schema["sha256"] = digest
    save_manifest(path, payload)


def expect_fail(root, label):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--root", str(root)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 or result.stdout.strip() != "FAIL " + label:
        print("FAIL negative " + label)
        print(result.stdout)
        return 1
    if "T050 PASS" in result.stdout or "A09 PASS" in result.stdout:
        print("FAIL negative printed an admission")
        return 1
    print("PASS negative " + label.split(":", 1)[0])
    return 0


def self_check():
    good = subprocess.run([sys.executable, str(Path(__file__).resolve())], capture_output=True, text=True)
    if good.returncode != 0 or "OFFLINE_SCHEMA_INTEGRITY_VERIFIED files=16" not in good.stdout:
        print("FAIL live manifest")
        print(good.stdout)
        print(good.stderr)
        return 1
    if "RUNTIME_PRODUCER_NOT_ADMITTED" not in good.stdout or "T050 PASS" in good.stdout or "A09 PASS" in good.stdout:
        print("FAIL live manifest admission line")
        return 1
    print("PASS live_manifest files=16")

    cases = []

    tamper = mutate_copy()
    target = tamper / "contracts/arcava/CT-ARC-002/1.0/request.schema.json"
    target.write_bytes(target.read_bytes().replace(b"request", b"requesT", 1))
    cases.append((tamper, "digest mismatch"))

    substituted = mutate_copy()
    path, payload = manifest_of(substituted)
    payload["common_components"][0]["sha256"] = "0" * 64
    save_manifest(path, payload)
    cases.append((substituted, "digest mismatch"))

    missing = mutate_copy()
    (missing / "contracts/arcava/CT-ARC-002/1.0/error.schema.json").unlink()
    cases.append((missing, "schema file missing"))

    duplicate = mutate_copy()
    path, payload = manifest_of(duplicate)
    payload["common_components"].append(dict(payload["common_components"][0]))
    save_manifest(path, payload)
    cases.append((duplicate, "duplicate path"))

    wrong_id = mutate_copy()
    path, payload = manifest_of(wrong_id)
    payload["contracts"][0]["contract_id"] = "CT-ARC-999"
    save_manifest(path, payload)
    cases.append((wrong_id, "contract id rejected"))

    wrong_kind = mutate_copy()
    path, payload = manifest_of(wrong_kind)
    payload["contracts"][0]["physical_schemas"][0]["kind"] = "query"
    save_manifest(path, payload)
    cases.append((wrong_kind, "schema kind rejected"))

    wrong_version = mutate_copy()
    path, payload = manifest_of(wrong_version)
    payload["contracts"][0]["profile_version"] = "2.0"
    save_manifest(path, payload)
    cases.append((wrong_version, "version rejected"))

    escaped = mutate_copy()
    path, payload = manifest_of(escaped)
    payload["contracts"][0]["physical_schemas"][0]["path"] = "contracts/arcava/../../etc/passwd"
    save_manifest(path, payload)
    cases.append((escaped, "path escape"))

    broken = mutate_copy()
    relative = "contracts/arcava/CT-ARC-002/1.0/request.schema.json"
    (broken / relative).write_bytes(b"{not json")
    retarget_digest(broken, relative)
    cases.append((broken, "schema json rejected"))

    invalid = mutate_copy()
    (invalid / relative).write_text(
        json.dumps(
            {
                "$schema": DRAFT,
                "$id": "urn:arcava:CT-ARC-002:1.0:request",
                "type": "nope",
            }
        )
    )
    retarget_digest(invalid, relative)
    cases.append((invalid, "schema draft rejected"))

    mismatched = mutate_copy()
    document = json.loads((mismatched / relative).read_text())
    document["$id"] = "urn:arcava:CT-ARC-002:1.0:other"
    (mismatched / relative).write_text(json.dumps(document))
    retarget_digest(mismatched, relative)
    cases.append((mismatched, "schema id mismatch"))

    producer = mutate_copy()
    path, payload = manifest_of(producer)
    payload["contracts"][0]["producer"] = "OTHER"
    save_manifest(path, payload)
    cases.append((producer, "producer rejected"))

    ready = mutate_copy()
    path, payload = manifest_of(ready)
    payload["contracts"][0]["runtime_producer_ready"] = True
    save_manifest(path, payload)
    cases.append((ready, "runtime producer admission rejected"))

    remote_ref = mutate_copy()
    document = json.loads((remote_ref / relative).read_text())
    document["$ref"] = "https://example.invalid/schema"
    (remote_ref / relative).write_text(json.dumps(document))
    retarget_digest(remote_ref, relative)
    cases.append((remote_ref, "schema ref not verified: https://example.invalid/schema"))

    for root, label in cases:
        if expect_fail(root, label):
            return 1
    print("PASS arcava_contract_manifest_negative")
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        return self_check()
    root = ROOT
    if len(sys.argv) == 3 and sys.argv[1] == "--root":
        root = Path(sys.argv[2])
    elif len(sys.argv) != 1:
        print("usage: validate_arcava_contract_manifest.py [--self-check|--root PATH]", file=sys.stderr)
        return 2
    error = validate(root)
    if error:
        print("FAIL " + error)
        return 1
    print("OFFLINE_SCHEMA_INTEGRITY_VERIFIED files=16")
    print("RUNTIME_PRODUCER_NOT_ADMITTED")
    print("PASS arcava_contract_manifest files=16")
    return 0


if __name__ == "__main__":
    sys.exit(main())
