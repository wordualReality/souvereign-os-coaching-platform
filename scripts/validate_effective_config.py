#!/usr/bin/env python3
"""Check one effective-config object against docs/arcava/config/environment.schema.json."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "arcava" / "config" / "environment.schema.json"


def load_schema():
    return json.loads(SCHEMA_PATH.read_text())


def check(schema, candidate):
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


def self_check():
    schema = load_schema()
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
    ]
    for name, candidate, expected in cases:
        actual = check(schema, candidate)
        if actual != expected:
            print("FAIL " + name)
            return 1
        print("PASS " + name)
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
