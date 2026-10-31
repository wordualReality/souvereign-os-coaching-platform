#!/usr/bin/env python3
"""Check one effective-config object against docs/arcava/config/environment.schema.json."""

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "arcava" / "config" / "environment.schema.json"
SCHEMA_KEYS = {
    "$schema",
    "$id",
    "title",
    "description",
    "type",
    "additionalProperties",
    "required",
    "properties",
    "x-not-read-by-active-listener",
    "x-runtime",
}
PROPERTY_RULES = {"type", "enum", "const", "minLength", "minimum", "maximum", "description", "x-sensitivity"}
PROPERTY_TYPES = {"string", "integer"}


def load_schema():
    return json.loads(SCHEMA_PATH.read_text())


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def value_matches(expected, value):
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return is_int(value)
    return False


def rule_error(key, rule):
    if not isinstance(rule, dict):
        return "schema rule rejected: " + key
    unknown = sorted(name for name in rule if name not in PROPERTY_RULES)
    if unknown:
        return "schema rule rejected: " + key + " " + unknown[0]
    if "type" not in rule:
        return "schema type missing: " + key
    expected = rule["type"]
    if expected not in PROPERTY_TYPES:
        return "schema type rejected: " + key
    if "description" in rule and not isinstance(rule["description"], str):
        return "schema rule rejected: " + key + " description"
    if "x-sensitivity" in rule and not isinstance(rule["x-sensitivity"], str):
        return "schema rule rejected: " + key + " x-sensitivity"
    if expected == "string" and ("minimum" in rule or "maximum" in rule):
        return "schema constraint rejected: " + key
    if expected == "integer" and "minLength" in rule:
        return "schema constraint rejected: " + key
    if "minLength" in rule and (not is_int(rule["minLength"]) or rule["minLength"] < 0):
        return "schema constraint rejected: " + key
    if "minimum" in rule and not is_int(rule["minimum"]):
        return "schema constraint rejected: " + key
    if "maximum" in rule and not is_int(rule["maximum"]):
        return "schema constraint rejected: " + key
    if "minimum" in rule and "maximum" in rule and rule["minimum"] > rule["maximum"]:
        return "schema constraint rejected: " + key
    if "enum" in rule:
        enum = rule["enum"]
        if not isinstance(enum, list) or not enum or any(not value_matches(expected, item) for item in enum):
            return "schema enum rejected: " + key
    if "const" in rule and not value_matches(expected, rule["const"]):
        return "schema const rejected: " + key
    if "enum" in rule and "const" in rule and rule["const"] not in rule["enum"]:
        return "schema constraint rejected: " + key
    return None


def schema_error(schema):
    if not isinstance(schema, dict):
        return "schema must be an object"
    unknown = sorted(key for key in schema if key not in SCHEMA_KEYS)
    if unknown:
        return "schema rule rejected: " + unknown[0]
    if schema.get("type") != "object":
        return "schema type rejected: root"
    if schema.get("additionalProperties") is not False:
        return "schema additionalProperties rejected"
    if not isinstance(schema.get("required"), list):
        return "schema required rejected"
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        return "schema properties rejected"
    for key, rule in properties.items():
        error = rule_error(key, rule)
        if error:
            return error
    for key in schema["required"]:
        if key not in properties:
            return "schema required missing property: " + key
    return None


def check(schema, candidate):
    error = schema_error(schema)
    if error:
        return error
    if not isinstance(candidate, dict):
        return "candidate must be an object"
    properties = schema["properties"]
    extra = [key for key in candidate if key not in properties]
    if extra:
        return "additional property rejected"
    for key in schema["required"]:
        if key not in candidate:
            return "required key missing: " + key
    for key, value in candidate.items():
        rule = properties[key]
        expected = rule["type"]
        if not value_matches(expected, value):
            return "type mismatch: " + key
        if "enum" in rule and value not in rule["enum"]:
            return "enum rejected: " + key
        if "const" in rule and value != rule["const"]:
            return "const rejected: " + key
        if "minLength" in rule and len(value) < rule["minLength"]:
            return "minLength rejected: " + key
        if "minimum" in rule and value < rule["minimum"]:
            return "range rejected: " + key
        if "maximum" in rule and value > rule["maximum"]:
            return "range rejected: " + key
    return None


def previous_check(schema, candidate):
    """The checker before this package. It ignores unknown rules and missing types raise KeyError."""
    if not isinstance(candidate, dict):
        return "candidate must be an object"
    properties = schema["properties"]
    extra = [key for key in candidate if key not in properties]
    if extra:
        return "additional property rejected"
    for key in schema["required"]:
        if key not in candidate:
            return "required key missing: " + key
    for key, value in candidate.items():
        rule = properties[key]
        expected = rule["type"]
        if expected == "string" and not isinstance(value, str):
            return "type mismatch: " + key
        if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            return "type mismatch: " + key
        if "enum" in rule and value not in rule["enum"]:
            return "enum rejected: " + key
        if "const" in rule and value != rule["const"]:
            return "const rejected: " + key
        if "minLength" in rule and len(value) < rule["minLength"]:
            return "minLength rejected: " + key
        if "minimum" in rule and value < rule["minimum"]:
            return "range rejected: " + key
        if "maximum" in rule and value > rule["maximum"]:
            return "range rejected: " + key
    return None


def expect(schema, candidate, expected, name):
    actual = check(schema, candidate)
    if actual != expected:
        print("FAIL " + name + " actual=" + str(actual))
        return 1
    print("PASS " + name)
    return 0


def self_check():
    schema = load_schema()
    if schema_error(schema):
        print("FAIL live schema " + schema_error(schema))
        return 1
    valid = {
        "SERVER_ADDRESS": "127.0.0.1",
        "SERVER_PORT": 8080,
        "ARCAVA_JOURNAL_PATH": "synthetic-journal",
        "ARCAVA_RUNTIME_ROLE": "ACTIVE_DEV_HTTP",
        "SPRING_PROFILES_ACTIVE": "dev",
    }
    cases = [
        ("valid", valid, None),
        ("non_loopback", {**valid, "SERVER_ADDRESS": "0.0.0.0"}, "enum rejected: SERVER_ADDRESS"),
        ("missing_journal", {k: v for k, v in valid.items() if k != "ARCAVA_JOURNAL_PATH"}, "required key missing: ARCAVA_JOURNAL_PATH"),
        ("wrong_role", {**valid, "ARCAVA_RUNTIME_ROLE": "OTHER"}, "const rejected: ARCAVA_RUNTIME_ROLE"),
        ("empty_journal", {**valid, "ARCAVA_JOURNAL_PATH": ""}, "minLength rejected: ARCAVA_JOURNAL_PATH"),
        ("port_range", {**valid, "SERVER_PORT": 70000}, "range rejected: SERVER_PORT"),
        ("forbidden_extra", {**valid, "DATABASE_URL": "redacted-sentinel"}, "additional property rejected"),
        ("malformed_candidate", ["not-an-object"], "candidate must be an object"),
    ]
    for name, candidate, expected in cases:
        if expect(schema, candidate, expected, name):
            return 1

    unused = copy.deepcopy(schema)
    unused["properties"]["UNUSED_NOTE"] = {"type": "string", "pattern": "^x$"}
    if previous_check(unused, valid) is not None:
        print("FAIL previous checker did not ignore the unused pattern")
        return 1
    if expect(unused, valid, "schema rule rejected: UNUSED_NOTE pattern", "unused_pattern"):
        return 1
    for keyword, body in (
        ("maxLength", {"type": "string", "maxLength": 3}),
        ("format", {"type": "string", "format": "date-time"}),
    ):
        drifted = copy.deepcopy(schema)
        drifted["properties"]["UNUSED_NOTE"] = body
        if expect(drifted, valid, "schema rule rejected: UNUSED_NOTE " + keyword, "unused_" + keyword):
            return 1

    boolean_type = copy.deepcopy(schema)
    boolean_type["properties"]["FLAG"] = {"type": "boolean"}
    if previous_check(boolean_type, valid) is not None:
        print("FAIL previous checker did not ignore the boolean type")
        return 1
    if expect(boolean_type, valid, "schema type rejected: FLAG", "unknown_type"):
        return 1

    missing_type = copy.deepcopy(schema)
    missing_type["properties"]["FLAG"] = {"description": "unused"}
    if previous_check(missing_type, valid) is not None:
        print("FAIL previous checker did not ignore a missing type on an unused property")
        return 1
    try:
        previous_check(missing_type, {**valid, "FLAG": "on"})
    except KeyError:
        pass
    else:
        print("FAIL previous checker did not raise on a missing type")
        return 1
    if expect(missing_type, valid, "schema type missing: FLAG", "missing_type"):
        return 1

    bounds = copy.deepcopy(schema)
    bounds["properties"]["SERVER_PORT"]["minimum"] = 10
    bounds["properties"]["SERVER_PORT"]["maximum"] = 1
    if expect(bounds, valid, "schema constraint rejected: SERVER_PORT", "inverted_bounds"):
        return 1

    empty_enum = copy.deepcopy(schema)
    empty_enum["properties"]["SERVER_PORT"]["enum"] = []
    if expect(empty_enum, valid, "schema enum rejected: SERVER_PORT", "empty_enum"):
        return 1

    bad_const = copy.deepcopy(schema)
    bad_const["properties"]["ARCAVA_RUNTIME_ROLE"]["enum"] = ["OTHER"]
    if expect(bad_const, valid, "schema constraint rejected: ARCAVA_RUNTIME_ROLE", "const_outside_enum"):
        return 1

    opened = copy.deepcopy(schema)
    opened["patternProperties"] = {".*": {"type": "string"}}
    if previous_check(opened, valid) is not None:
        print("FAIL previous checker did not ignore patternProperties")
        return 1
    if expect(opened, valid, "schema rule rejected: patternProperties", "schema_structure"):
        return 1

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        valid_path = root / "valid.json"
        extra_path = root / "extra.json"
        malformed_path = root / "malformed.json"
        valid_path.write_text(json.dumps(valid))
        extra_path.write_text(json.dumps({**valid, "DATABASE_URL": "redacted-sentinel"}))
        malformed_path.write_text("[1]")
        script = str(Path(__file__).resolve())
        valid_run = subprocess.run([sys.executable, script, str(valid_path)], capture_output=True, text=True)
        extra_run = subprocess.run([sys.executable, script, str(extra_path)], capture_output=True, text=True)
        malformed_run = subprocess.run([sys.executable, script, str(malformed_path)], capture_output=True, text=True)
    if valid_run.returncode != 0 or valid_run.stdout.strip() != "PASS effective_config":
        print("FAIL cli valid exit")
        return 1
    print("PASS cli_valid_exit")
    if extra_run.returncode != 1 or extra_run.stdout.strip() != "FAIL additional property rejected":
        print("FAIL cli candidate exit")
        return 1
    print("PASS cli_candidate_exit")
    if malformed_run.returncode != 1 or malformed_run.stdout.strip() != "FAIL candidate must be an object":
        print("FAIL cli malformed exit")
        return 1
    print("PASS cli_malformed_exit")
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        return self_check()
    if len(sys.argv) != 2:
        print("usage: validate_effective_config.py <candidate.json> | --self-check", file=sys.stderr)
        return 2
    schema = load_schema()
    candidate = json.loads(Path(sys.argv[1]).read_text())
    error = check(schema, candidate)
    if error:
        print("FAIL " + error)
        return 1
    print("PASS effective_config")
    return 0


if __name__ == "__main__":
    sys.exit(main())
