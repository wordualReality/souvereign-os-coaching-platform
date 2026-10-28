#!/usr/bin/env python3
"""Compare the source pins with the local tools. This is not an owner admission."""

import json
import re
import shutil
import subprocess
import sys
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
    parent = re.search(r"<artifactId>spring-boot-starter-parent</artifactId>\s*<version>([^<]+)</version>", text)
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


def tool_version(command):
    binary = shutil.which(command[0])
    if binary is None:
        return "ABSENT"
    result = subprocess.run(command, capture_output=True, text=True)
    return (result.stdout + result.stderr).strip().splitlines()[0]


def main():
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
    java_line = tool_version(["java", "-version"])
    node_line = tool_version(["node", "-v"])
    print(
        "TOOLCHAIN java_release=25 spring=4.1.1 maven_pin=3.9.16 node_pin=20.12.2 "
        "next=16.4.3 react=19.3.1 typescript=7.0.2"
    )
    print("LOCAL_JAVA " + java_line)
    print("LOCAL_NODE " + node_line)
    if OWNER_PIN.is_file():
        print("ADMISSION OWNER_PIN_PRESENT path=" + str(OWNER_PIN.relative_to(ROOT)))
    else:
        print("ADMISSION PROPOSAL_EXERCISED_NOT_ADMITTED")
        print("OWNER_PIN missing path=docs/arcava/admission/toolchain-owner-pin.json")
        print(
            "EVIDENCE_REQUEST an owner receipt that names Java 25, Maven 3.9.16, "
            "Spring Boot 4.1.1, Node 20.12.2, Next 16.4.3, React 19.3.1 and TypeScript 7.0.2"
        )
    print("MAVEN_TESTS observed=10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
