#!/usr/bin/env python3
"""Source pin inventory and executable toolchain check. Neither mode admits an owner pin."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER_PIN = ROOT / "docs" / "arcava" / "admission" / "toolchain-owner-pin.json"


def read(path):
    return (ROOT / path).read_text()


def require(condition, message):
    if not condition:
        print("FAIL " + message)
        sys.exit(1)


def pin_from_pom():
    text = read("services/api/pom.xml")
    parent = re.search(
        r"<artifactId>spring-boot-starter-parent</artifactId>\s*<version>([^<]+)</version>",
        text,
    )
    java = re.search(r"<java.version>([^<]+)</java.version>", text)
    require(parent is not None and java is not None, "pom pins are unreadable")
    return parent.group(1), java.group(1)


def pin_from_node():
    package = json.loads(read("package.json"))
    lock = json.loads(read("package-lock.json"))
    deps = package["dependencies"]
    dev = package["devDependencies"]
    locked = {
        "next": lock["packages"]["node_modules/next"]["version"],
        "react": lock["packages"]["node_modules/react"]["version"],
        "react-dom": lock["packages"]["node_modules/react-dom"]["version"],
        "typescript": lock["packages"]["node_modules/typescript"]["version"],
    }
    require(locked["next"] == deps["next"], "next lock differs from package.json")
    require(locked["react"] == deps["react"], "react lock differs from package.json")
    require(locked["react-dom"] == deps["react-dom"], "react-dom lock differs from package.json")
    require(locked["typescript"] == dev["typescript"], "typescript lock differs from package.json")
    return locked


def pin_from_workflows():
    contract = read(".github/workflows/ci.yml")
    kernel = read(".github/workflows/arcava-journey-kernel.yml")
    node = re.search(r"node-version: '([^']+)'", contract)
    maven = re.search(r"apache-maven-([0-9.]+)", kernel)
    java = re.search(r"java-version: '([^']+)'", kernel)
    require(node and maven and java, "workflow pins are unreadable")
    return node.group(1), maven.group(1), java.group(1)


def check_source_pins():
    spring, java_release = pin_from_pom()
    locked = pin_from_node()
    node_pin, maven_pin, workflow_java = pin_from_workflows()
    manifest = json.loads(read("docs/arcava/admission/toolchain-manifest.json"))
    require(manifest["commands"]["maven_tests"] == "10 tests, 0 failures", "manifest still records 8 Maven tests")
    require(java_release == "25" and workflow_java == "25", "Java release is not 25")
    require(spring == "4.1.1", "Spring Boot pin is not 4.1.1")
    require(maven_pin == "3.9.16", "workflow Maven pin is not 3.9.16")
    require(node_pin == "20.12.2", "workflow Node pin is not 20.12.2")
    require(locked["next"] == "16.4.3" and locked["react"] == "19.3.1", "frontend lock drifted")
    require(locked["typescript"] == "7.0.2", "typescript lock drifted")
    print(
        "TOOLCHAIN java_release=25 spring=4.1.1 maven_pin=3.9.16 node_pin=20.12.2 "
        "next=16.4.3 react=19.3.1 typescript=7.0.2"
    )
    print("MAVEN_TESTS observed=10")


def pin_path():
    override = os.environ.get("TOOLCHAIN_OWNER_PIN")
    if override:
        return Path(override)
    return OWNER_PIN


def admission_lines(path):
    lines = ["ADMISSION PROPOSAL_EXERCISED_NOT_ADMITTED"]
    if not path.is_file():
        lines.append("OWNER_PIN missing path=docs/arcava/admission/toolchain-owner-pin.json")
        lines.append(
            "EVIDENCE_REQUEST an owner receipt that names Java 25, Maven 3.9.16, "
            "Spring Boot 4.1.1, Node 20.12.2, Next 16.4.3, React 19.3.1 and TypeScript 7.0.2 "
            "with source_repo, source_revision, owner, revision_digest and authorization"
        )
        return lines, False
    forged = False
    try:
        payload = json.loads(path.read_text())
        forged = isinstance(payload, dict) and payload.get("owner_admitted") is True
    except (OSError, json.JSONDecodeError):
        payload = None
    rejected = "OWNER_PIN_REJECTED reason=local_file_is_not_an_owner_receipt"
    if forged:
        rejected += " forged_boolean=rejected"
    lines.append(rejected)
    lines.append(
        "OWNER_PIN_REQUIRED fields=source_repo,source_revision,owner,versions,revision_digest,authorization"
    )
    return lines, True


def probe(binary, args, env, timeout=10):
    found = shutil.which(binary, path=env.get("PATH", ""))
    if found is None:
        return "ABSENT", None
    try:
        result = subprocess.run(
            [found, *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT", None
    except OSError:
        return "ERROR", None
    if result.returncode != 0:
        return "EXIT", result.returncode
    text = (result.stdout + "\n" + result.stderr).strip()
    if not text:
        return "INVALID", None
    return "OK", text


def parse_java(text):
    match = re.search(r'version "(\d+)', text or "")
    return match.group(1) if match else None


def parse_maven(text):
    match = re.search(r"Apache Maven (\d+\.\d+\.\d+)", text or "")
    return match.group(1) if match else None


def parse_node(text):
    match = re.search(r"v(\d+\.\d+\.\d+)", text or "")
    return match.group(1) if match else None


TOOLS = {
    "java": {"bin": "java", "args": ["-version"], "parse": parse_java, "expected": "25"},
    "maven": {"bin": "mvn", "args": ["-v"], "parse": parse_maven, "expected": "3.9.16"},
    "node": {"bin": "node", "args": ["-v"], "parse": parse_node, "expected": "20.12.2"},
}


def observe(tool, env):
    spec = TOOLS[tool]
    state, detail = probe(spec["bin"], spec["args"], env)
    if state != "OK":
        return state, detail
    version = spec["parse"](detail)
    if version == spec["expected"]:
        return "MATCH", version
    return "MISMATCH", version or "unparsed"


def print_admission():
    lines, rejected = admission_lines(pin_path())
    for line in lines:
        print(line)
    return rejected


def inventory(env):
    check_source_pins()
    for tool in ("java", "maven", "node"):
        state, version = observe(tool, env)
        if state == "MATCH":
            print("LOCAL_" + tool.upper() + " OBSERVED " + str(version))
        elif state == "MISMATCH":
            print("LOCAL_" + tool.upper() + " MISMATCH " + str(version))
        else:
            suffix = "" if version is None else " " + str(version)
            print("LOCAL_" + tool.upper() + " " + state + suffix)
    print("RUNTIME_CHECK skipped reason=inventory_mode")
    rejected = print_admission()
    if rejected:
        print("FAIL owner pin file is not an admission")
        return 1
    return 0


def runtime(tools, env):
    check_source_pins()
    failed = False
    for tool in tools:
        state, version = observe(tool, env)
        if state == "MATCH":
            print("RUNTIME " + tool + "=" + version + " PASS")
        else:
            failed = True
            print("FAIL RUNTIME " + tool + "=" + state + " observed=" + str(version))
    if failed:
        return 1
    print("RUNTIME_PASS tools=" + ",".join(tools))
    if print_admission():
        print("FAIL owner pin file is not an admission")
        return 1
    return 0


def write_tool(directory, name, body):
    path = directory / name
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)


def run_child(args, env):
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def self_check():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        good = root / "good"
        bad = root / "bad"
        empty = root / "empty"
        good.mkdir()
        bad.mkdir()
        empty.mkdir()
        write_tool(good, "java", 'echo \'openjdk version "25.0.3" 2026-04-21 LTS\' >&2')
        write_tool(good, "mvn", 'echo "Apache Maven 3.9.16"')
        write_tool(good, "node", 'echo "v20.12.2"')
        write_tool(bad, "java", 'echo \'openjdk version "21.0.2"\' >&2')
        write_tool(bad, "mvn", 'echo "Apache Maven 3.8.8"')
        write_tool(bad, "node", 'echo "v18.20.0"')
        forged = root / "toolchain-owner-pin.json"
        forged.write_text('{"owner_admitted": true, "java": "25", "maven": "3.9.16"}')
        base = os.environ.copy()
        base.pop("TOOLCHAIN_OWNER_PIN", None)

        absent_env = base.copy()
        absent_env["PATH"] = str(empty)
        absent = run_child([], absent_env)
        if absent.returncode != 0 or "LOCAL_JAVA ABSENT" not in absent.stdout or "RUNTIME_PASS" in absent.stdout:
            print("FAIL inventory treated an absent java as a runtime pass")
            print(absent.stdout)
            return 1

        mismatch_env = base.copy()
        mismatch_env["PATH"] = str(bad)
        mismatch = run_child(["--runtime", "java,maven,node"], mismatch_env)
        if mismatch.returncode == 0 or "FAIL RUNTIME java=MISMATCH" not in mismatch.stdout:
            print("FAIL a mismatched java was accepted")
            print(mismatch.stdout)
            return 1
        if "FAIL RUNTIME maven=MISMATCH" not in mismatch.stdout or "FAIL RUNTIME node=MISMATCH" not in mismatch.stdout:
            print("FAIL a mismatched maven or node was accepted")
            print(mismatch.stdout)
            return 1

        missing_env = base.copy()
        missing_env["PATH"] = str(empty)
        missing = run_child(["--runtime", "java,maven"], missing_env)
        if missing.returncode == 0 or "FAIL RUNTIME java=ABSENT" not in missing.stdout:
            print("FAIL a missing java was accepted")
            print(missing.stdout)
            return 1
        if "FAIL RUNTIME maven=ABSENT" not in missing.stdout:
            print("FAIL a missing maven was accepted")
            print(missing.stdout)
            return 1
        missing_node = run_child(["--runtime", "node"], missing_env)
        if missing_node.returncode == 0 or "FAIL RUNTIME node=ABSENT" not in missing_node.stdout:
            print("FAIL a missing node was accepted")
            print(missing_node.stdout)
            return 1

        exit7 = root / "exit7"
        exit7.mkdir()
        write_tool(exit7, "java", "echo 'openjdk version \"25.0.3\"' >&2\nexit 7")
        write_tool(exit7, "mvn", 'echo "Apache Maven 3.9.16"\nexit 7')
        write_tool(exit7, "node", 'echo "v20.12.2"\nexit 7')
        exit_env = base.copy()
        exit_env["PATH"] = str(exit7)
        exited = run_child(["--runtime", "java,maven,node"], exit_env)
        if exited.returncode == 0 or "RUNTIME java=25 PASS" in exited.stdout or "RUNTIME_PASS" in exited.stdout:
            print("FAIL exit 7 with a matching version was accepted")
            print(exited.stdout)
            return 1
        for tool in ("java", "maven", "node"):
            if "FAIL RUNTIME " + tool + "=EXIT observed=7" not in exited.stdout:
                print("FAIL " + tool + " exit 7 was not rejected")
                print(exited.stdout)
                return 1

        invalid = root / "invalid"
        invalid.mkdir()
        write_tool(invalid, "java", 'echo "not-a-version"')
        invalid_env = base.copy()
        invalid_env["PATH"] = str(invalid)
        invalid_run = run_child(["--runtime", "java"], invalid_env)
        if invalid_run.returncode == 0 or "FAIL RUNTIME java=MISMATCH" not in invalid_run.stdout:
            print("FAIL invalid java output was accepted")
            print(invalid_run.stdout)
            return 1

        hang = root / "hang"
        hang.mkdir()
        write_tool(hang, "java", "while true; do :; done")
        hang_env = base.copy()
        hang_env["PATH"] = str(hang)
        hang_state, _detail = probe("java", ["-version"], hang_env, timeout=0.4)
        if hang_state != "TIMEOUT":
            print("FAIL a hung java was not a timeout")
            return 1

        good_env = base.copy()
        good_env["PATH"] = str(good)
        matched = run_child(["--runtime", "java,maven,node"], good_env)
        if matched.returncode != 0 or "RUNTIME_PASS tools=java,maven,node" not in matched.stdout:
            print("FAIL matching binaries did not pass the runtime check")
            print(matched.stdout)
            print(matched.stderr)
            return 1
        if "ADMISSION PROPOSAL_EXERCISED_NOT_ADMITTED" not in matched.stdout:
            print("FAIL a version match was treated as owner admission")
            return 1

        forged_env = good_env.copy()
        forged_env["TOOLCHAIN_OWNER_PIN"] = str(forged)
        forged_run = run_child(["--runtime", "java"], forged_env)
        if forged_run.returncode == 0 or "forged_boolean=rejected" not in forged_run.stdout:
            print("FAIL a forged owner pin was accepted")
            print(forged_run.stdout)
            return 1
        if "ADMISSION PROPOSAL_EXERCISED_NOT_ADMITTED" not in forged_run.stdout:
            print("FAIL a forged owner pin changed the admission")
            return 1
    print(
        "PASS toolchain_runtime_negative missing=fail missing_node=fail mismatch=fail "
        "exit_status=fail invalid=fail timeout=fail forged_pin=rejected "
        "inventory_absent=not_a_runtime_pass"
    )
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        return self_check()
    if len(sys.argv) == 3 and sys.argv[1] == "--runtime":
        tools = [item.strip() for item in sys.argv[2].split(",") if item.strip()]
        require(tools and all(tool in TOOLS for tool in tools), "runtime tools must be java, maven or node")
        return runtime(tools, os.environ.copy())
    if len(sys.argv) != 1:
        print("FAIL usage: toolchain_receipt.py [--self-check|--runtime java,maven,node]")
        return 1
    return inventory(os.environ.copy())


if __name__ == "__main__":
    sys.exit(main())
