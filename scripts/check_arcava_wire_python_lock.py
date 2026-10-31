#!/usr/bin/env python3
"""Check the Arcava wire-test lock and fail closed on a bad install.

The lock is a source-bounded test dependency candidate. It is not an ARC-10
toolchain owner pin, and a successful install is not T150 admission.
"""

import hashlib
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "docs" / "arcava" / "admission" / "wire-python-deps.lock"
PINS = (
    "attrs==26.1.0",
    "jsonschema==4.26.0",
    "jsonschema-specifications==2025.9.1",
    "referencing==0.37.0",
    "rpds-py==2026.9.1",
    "typing-extensions==4.16.0",
)
CI_LINUX_WHEEL = "addeda51556dac7c1a2f14cda62db8b621cd12afba3091d03a96c72932387eab"
MAC_ARM_WHEEL = "3f0e9ac28fc067d4d34b88ae43c48e9489455c97fee9633d851f7eeed5a05d35"
WIN32_ONLY = "befc2d6a953e563f8a7bfd87a42c22ebf8a3e980dcb7b6a4d17b70b0e914e8a3"
JSONSCHEMA_WHEEL = "d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce"
NAMES = (
    "jsonschema",
    "attrs",
    "jsonschema-specifications",
    "referencing",
    "rpds-py",
    "typing-extensions",
)


def fail(message):
    print(f"FAIL wire_python_lock {message}")
    return 1


def redact(text):
    for key in ("HOME", "RUNNER_TEMP", "TMPDIR"):
        value = os.environ.get(key)
        if value:
            text = text.replace(value, f"${key}")
    return text


def requirements(text):
    items = []
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            line = line[:-1].strip()
            continued = True
        else:
            continued = False
        if line.startswith("--hash=sha256:"):
            if current is None:
                raise ValueError("hash outside requirement")
            current[2].append(line.split(":", 1)[1])
        elif "==" in line and not line.startswith("--"):
            if current is not None:
                items.append(current)
            name, version = line.split("==", 1)
            current = [name, version, []]
        else:
            raise ValueError(f"unsupported lock line {line}")
        if current is not None and not continued and current[2]:
            items.append(current)
            current = None
    if current is not None:
        items.append(current)
    return items


def check_lock(text):
    if "owner_admitted" in text or "TOOLCHAIN_ADMITTED" in text:
        return fail("lock claims toolchain admission")
    if "/Users/" in text or "SovereignDelivery" in text:
        return fail("lock contains a local path")
    try:
        items = requirements(text)
    except ValueError as error:
        return fail(str(error))
    found = {}
    seen = set()
    for name, version, hashes in items:
        pin = f"{name}=={version}"
        if name in seen or pin in found:
            return fail(f"duplicate package {name}")
        seen.add(name)
        if len(hashes) < 1:
            return fail(f"missing hashes {pin}")
        for digest in hashes:
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                return fail(f"invalid hash {name}")
        found[pin] = hashes
    if len(items) != len(PINS):
        return fail(f"requirement count {len(items)}")
    if set(found) != set(PINS):
        return fail("pin set mismatch")
    if CI_LINUX_WHEEL not in text or MAC_ARM_WHEEL not in text:
        return fail("platform wheel hash missing")
    if WIN32_ONLY not in text:
        return fail("control wheel hash missing")
    print("PASS wire_python_lock structure pins=6")
    print("STRUCTURE_EXACT count=6")
    print("CI_WHEEL_HASH_PRESENT rpds_py cp312 manylinux_x86_64")
    print("MAC_WHEEL_HASH_PRESENT rpds_py cp314 macosx_arm64")
    print("PIN_CLASS SOURCE_BOUNDED_TEST_DEPENDENCY_PIN_CANDIDATE")
    print("TOOLCHAIN_OWNER_PIN_MISSING")
    print("A09_NOT_EXECUTED")
    print("IMAGE_REVISION_DYNAMIC")
    return 0


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True)


def expect_fail(label, cmd):
    result = run(cmd)
    if result.returncode == 0:
        print(redact(result.stdout[-500:] + result.stderr[-500:]))
        print(f"FAIL wire_python_lock {label} exit=0")
        return 1
    print(f"PASS wire_python_lock {label} exit={result.returncode}")
    return 0


def expect_structure_fail(label, mutated, expected):
    with tempfile.TemporaryDirectory(prefix="arcava-wire-structure-") as temporary:
        probe = Path(temporary) / "probe.lock"
        probe.write_text(mutated)
        code = (
            "import importlib.util, pathlib, sys\n"
            f"spec = importlib.util.spec_from_file_location('lockcheck', {str(Path(__file__))!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            f"text = pathlib.Path({str(probe)!r}).read_text()\n"
            "sys.exit(mod.check_lock(text))\n"
        )
        result = run([sys.executable, "-c", code])
    if result.returncode == 0 or expected not in result.stdout:
        print(redact(result.stdout[-400:] + result.stderr[-400:]))
        print(f"FAIL wire_python_lock {label} exit={result.returncode}")
        return 1
    print(f"PASS wire_python_lock {label} exit={result.returncode}")
    return 0


def venv_pip(root):
    path = root / "venv"
    created = run([sys.executable, "-m", "venv", str(path)])
    if created.returncode != 0:
        print(redact(created.stderr[-400:]))
        raise RuntimeError("venv")
    return path / "bin" / "pip", path / "bin" / "python"


def restrict_rpds(text):
    lines = []
    skipping = False
    inserted = False
    for raw in text.splitlines():
        if raw.startswith("rpds-py=="):
            lines.append("rpds-py==2026.9.1 \\")
            skipping = True
            continue
        if skipping and raw.strip().startswith("--hash="):
            if not inserted:
                lines.append(f"    --hash=sha256:{WIN32_ONLY}")
                inserted = True
            continue
        skipping = False
        lines.append(raw)
    if not inserted:
        raise RuntimeError("rpds section missing")
    return "\n".join(lines) + "\n"


def self_check():
    text = LOCK.read_text()
    status = check_lock(text)
    if status != 0:
        return status
    extra_hash = "ab" * 32
    extra = text.rstrip() + f"\narcava-wire-extra==1.0.0 \\\n    --hash=sha256:{extra_hash}\n"
    status = expect_structure_fail("extra_pin", extra, "requirement count")
    duplicate = text.rstrip() + f"\nattrs==26.1.0 \\\n    --hash=sha256:{'cd' * 32}\n"
    status |= expect_structure_fail("duplicate_pin", duplicate, "duplicate package")
    if status != 0:
        return status
    with tempfile.TemporaryDirectory(prefix="arcava-wire-lock-") as temporary:
        root = Path(temporary)
        pip, python = venv_pip(root)
        wheels = root / "wheels"
        wheels.mkdir()
        download = run(
            [
                str(pip),
                "download",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--require-hashes",
                "--only-binary=:all:",
                "-d",
                str(wheels),
                "-r",
                str(LOCK),
            ]
        )
        if download.returncode != 0:
            print(redact(download.stderr[-800:]))
            return fail("hashed download")
        fetched = sorted(wheels.glob("*.whl"))
        if not fetched or any(item.suffix != ".whl" for item in wheels.iterdir()):
            return fail("download was not wheels only")
        for item in fetched:
            digest = hashlib.sha256(item.read_bytes()).hexdigest()
            if digest not in text:
                return fail(f"downloaded hash absent {item.name}")
            print(f"WIRE_FETCH {item.name} sha256={digest}")
        install_root = root / "install"
        install_pip, install_python = venv_pip(install_root)
        installed = run(
            [
                str(install_pip),
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--no-index",
                "--find-links",
                str(wheels),
                "--require-hashes",
                "--only-binary=:all:",
                "-r",
                str(LOCK),
            ]
        )
        if installed.returncode != 0:
            print(redact(installed.stderr[-800:]))
            return fail("offline hashed install")
        shown = run(
            [
                str(install_python),
                "-c",
                "import importlib.metadata as md, platform, sys\n"
                "print('WIRE_PLATFORM python=' + sys.version.split()[0] + ' platform=' + sys.platform + ' machine=' + platform.machine())\n"
                + "".join(f"print('WIRE_DEP {name}==' + md.version({name!r}))\n" for name in NAMES),
            ]
        )
        if shown.returncode != 0:
            print(redact(shown.stderr[-400:]))
            return fail("import pinned distributions")
        print(shown.stdout.strip())
        print("PASS wire_python_lock install exit=0")

        tamper_dir = root / "tamper"
        tamper_dir.mkdir()
        target = next(item for item in fetched if item.name.startswith("rpds_py-"))
        original = target.read_bytes()
        flipped = bytearray(original)
        flipped[-1] ^= 0x01
        if hashlib.sha256(flipped).hexdigest() == hashlib.sha256(original).hexdigest():
            return fail("tamper did not change bytes")
        for item in fetched:
            destination = tamper_dir / item.name
            destination.write_bytes(flipped if item == target else item.read_bytes())
        tamper_venv = root / "tamper-venv"
        tamper_pip, _python = venv_pip(tamper_venv)
        status |= expect_fail(
            "tamper",
            [
                str(tamper_pip),
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--no-index",
                "--find-links",
                str(tamper_dir),
                "--require-hashes",
                "--only-binary=:all:",
                "-r",
                str(LOCK),
            ],
        )

        changed = root / "changed.lock"
        replacement = JSONSCHEMA_WHEEL[:-1] + ("0" if JSONSCHEMA_WHEEL[-1] != "0" else "1")
        needle = f"--hash=sha256:{JSONSCHEMA_WHEEL}"
        changed.write_text(text.replace(needle, f"--hash=sha256:{replacement}", 1))
        changed_venv = root / "changed-venv"
        changed_pip, _python = venv_pip(changed_venv)
        status |= expect_fail(
            "changed_hash",
            [
                str(changed_pip),
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--no-index",
                "--find-links",
                str(wheels),
                "--require-hashes",
                "--only-binary=:all:",
                "-r",
                str(changed),
            ],
        )

        unpinned = root / "unpinned.txt"
        unpinned.write_text("jsonschema==4.26.0\n")
        unpinned_venv = root / "unpinned-venv"
        unpinned_pip, _python = venv_pip(unpinned_venv)
        status |= expect_fail(
            "unpinned",
            [
                str(unpinned_pip),
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--require-hashes",
                "--no-index",
                "-r",
                str(unpinned),
            ],
        )

        unknown = root / "unknown.txt"
        unknown.write_text(
            "arcava-wire-unknown-pkg==9.9.9 \\\n"
            "    --hash=sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n"
        )
        (root / "empty").mkdir(exist_ok=True)
        unknown_venv = root / "unknown-venv"
        unknown_pip, _python = venv_pip(unknown_venv)
        status |= expect_fail(
            "unknown_package",
            [
                str(unknown_pip),
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--require-hashes",
                "--only-binary=:all:",
                "--no-index",
                "--find-links",
                str(root / "empty"),
                "-r",
                str(unknown),
            ],
        )

        narrowed = root / "narrow.lock"
        narrowed.write_text(restrict_rpds(text))
        narrow_venv = root / "narrow-venv"
        narrow_pip, _python = venv_pip(narrow_venv)
        status |= expect_fail(
            "unsupported_platform",
            [
                str(narrow_pip),
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--no-index",
                "--find-links",
                str(wheels),
                "--require-hashes",
                "--only-binary=:all:",
                "-r",
                str(narrowed),
            ],
        )
    if status != 0:
        return status
    print("PASS wire_python_lock self_check")
    print(f"LOCAL_PLATFORM python={platform.python_version()} system={platform.system()} machine={platform.machine()}")
    return 0


def main():
    if not LOCK.is_file():
        return fail("lock missing")
    if "--self-check" in sys.argv:
        return self_check()
    return check_lock(LOCK.read_text())


if __name__ == "__main__":
    sys.exit(main())
