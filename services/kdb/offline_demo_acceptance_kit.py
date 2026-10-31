"""P23 reproducible offline demo acceptance ZIP.

Packages the existing P22 seven-file synthetic demo with deterministic ZIP
metadata and verifies it without extracting untrusted archive paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any

from offline_review_demo_pack import (
    DEMO_ROOT,
    EVIDENCE_FILE,
    EVIDENCE_FILES,
    EVIDENCE_PACKET,
    _ensure_demo_root,
    demo_pack_files_with_evidence,
    write_demo_pack,
)
from review_handoff_preview import PreviewParseError, REPO_ROOT

PACKET = "KDB-M01-P23-REPRODUCIBLE-OFFLINE-DEMO-ACCEPTANCE-KIT-01"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_ARCHIVE_BYTES = 1_048_576
MAX_MEMBER_BYTES = 262_144


def _deny(code: str) -> None:
    raise PreviewParseError(code)


def _zip_path(path: str | Path, *, must_exist: bool) -> Path:
    raw = Path(str(path))
    if raw.is_absolute() or ".." in raw.parts or raw.suffix != ".zip":
        _deny("UNSAFE_ZIP_PATH")
    root = _ensure_demo_root()
    resolved = (REPO_ROOT / raw).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        _deny("UNSAFE_ZIP_PATH")
    if resolved.parent != root or resolved.is_symlink():
        _deny("UNSAFE_ZIP_PATH")
    if must_exist:
        if not resolved.is_file() or resolved.stat().st_size > MAX_ARCHIVE_BYTES:
            _deny("INVALID_ZIP")
    elif resolved.exists():
        _deny("OUTPUT_EXISTS")
    return resolved


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_acceptance_zip(
    baseline_path: str | Path,
    current_path: str | Path,
    work_item_id: str,
    source_path: str | Path,
    output_zip: str | Path,
    *,
    commit: str,
) -> dict[str, Any]:
    receipt = demo_pack_files_with_evidence(
        baseline_path, current_path, work_item_id, source_path, commit=commit
    )
    target = _zip_path(output_zip, must_exist=False)
    try:
        with zipfile.ZipFile(target, "x") as archive:
            for name in EVIDENCE_FILES:
                archive.writestr(_zip_info(name), receipt["artifacts"][name].encode("utf-8"))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    verified = verify_acceptance_zip(output_zip)
    return {**verified, "packet": PACKET, "output": str(target.relative_to(REPO_ROOT))}


def _read_verified(path: str | Path) -> tuple[dict[str, bytes], dict[str, Any], Path]:
    location = _zip_path(path, must_exist=True)
    try:
        with zipfile.ZipFile(location, "r") as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if names != list(EVIDENCE_FILES) or len(names) != len(set(names)):
                _deny("ZIP_FILE_SET_MISMATCH")
            files: dict[str, bytes] = {}
            for info in infos:
                pure = PurePosixPath(info.filename)
                mode = (info.external_attr >> 16) & 0o170000
                if (
                    pure.is_absolute()
                    or len(pure.parts) != 1
                    or ".." in pure.parts
                    or info.is_dir()
                    or mode == 0o120000
                    or info.flag_bits & 0x1
                    or info.file_size > MAX_MEMBER_BYTES
                ):
                    _deny("UNSAFE_ZIP_MEMBER")
                files[info.filename] = archive.read(info)
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        raise PreviewParseError("INVALID_ZIP") from exc
    try:
        manifest = json.loads(files["manifest.json"].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreviewParseError("INVALID_MANIFEST") from exc
    expected_hashed = set(EVIDENCE_FILES) - {"manifest.json"}
    hashes = manifest.get("files")
    if manifest.get("packet") != EVIDENCE_PACKET or not isinstance(hashes, dict) or set(hashes) != expected_hashed:
        _deny("INVALID_MANIFEST")
    for name in expected_hashed:
        actual = hashlib.sha256(files[name]).hexdigest()
        if hashes.get(name) != actual:
            _deny("ARTIFACT_SHA_MISMATCH")
    return files, manifest, location


def verify_acceptance_zip(path: str | Path) -> dict[str, Any]:
    files, manifest, location = _read_verified(path)
    return {
        "packet": PACKET,
        "zip_sha256": hashlib.sha256(location.read_bytes()).hexdigest(),
        "zip_size": location.stat().st_size,
        "file_count": len(files),
        "evidence_status": manifest.get("evidence_status"),
        "final_authority": "NOT_ADMITTED",
    }


def extract_verified_zip(path: str | Path, out_dir: str | Path) -> Path:
    files, _manifest, _location = _read_verified(path)
    artifacts = {name: data.decode("utf-8") for name, data in files.items()}
    return write_demo_pack(artifacts, out_dir)


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def _browser() -> str:
    candidates = (
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    for item in candidates:
        if item and Path(item).is_file():
            return item
    _deny("BROWSER_SMOKE_NOT_VERIFIED")


def _dump_dom(browser: str, page: Path, profile: Path) -> str:
    proc = subprocess.run(
        [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-background-networking", "--disable-sync", "--metrics-recording-only",
         f"--user-data-dir={profile}", "--dump-dom", page.as_uri()],
        text=True, capture_output=True, timeout=30, check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        _deny("BROWSER_SMOKE_NOT_VERIFIED")
    return proc.stdout


def browser_smoke(path: str | Path) -> dict[str, Any]:
    files, _manifest, _location = _read_verified(path)
    browser = _browser()
    with tempfile.TemporaryDirectory(prefix="kdb-p23-smoke-") as raw:
        root = Path(raw)
        for name, data in files.items():
            (root / name).write_bytes(data)
        index_dom = _dump_dom(browser, root / "index.html", root / "profile-index")
        links = _Links(); links.feed(index_dom)
        if "current.html" not in links.hrefs or "PREVIEW_ONLY" not in index_dom or "NOT_ADMITTED" not in index_dom:
            _deny("BROWSER_SMOKE_NOT_VERIFIED")
        current_dom = _dump_dom(browser, root / "current.html", root / "profile-current")
        current_links = _Links(); current_links.feed(current_dom)
        if EVIDENCE_FILE not in current_links.hrefs or "LOCAL_BYTES_AND_SPANS_BOUNDED" not in current_dom:
            _deny("BROWSER_SMOKE_NOT_VERIFIED")
        evidence_dom = _dump_dom(browser, root / EVIDENCE_FILE, root / "profile-evidence")
        if "LOCAL_BYTES_AND_SPANS_BOUNDED" not in evidence_dom or "NOT_ADMITTED" not in evidence_dom or "byte_start" not in evidence_dom:
            _deny("BROWSER_SMOKE_NOT_VERIFIED")
    return {
        "packet": PACKET,
        "browser_smoke": "PASS",
        "path": "index.html -> current.html -> current-case-evidence.json",
        "network_dependency": "NONE",
        "final_authority": "NOT_ADMITTED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the P23 offline acceptance ZIP.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("baseline_json"); build.add_argument("current_json")
    build.add_argument("--work-item-id", required=True); build.add_argument("--source-file", required=True)
    build.add_argument("--output", required=True); build.add_argument("--commit", required=True)
    verify = sub.add_parser("verify"); verify.add_argument("zip")
    smoke = sub.add_parser("smoke"); smoke.add_argument("zip")
    extract = sub.add_parser("extract"); extract.add_argument("zip"); extract.add_argument("out_dir")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_acceptance_zip(args.baseline_json, args.current_json, args.work_item_id,
                                          args.source_file, args.output, commit=args.commit)
        elif args.command == "verify": result = verify_acceptance_zip(args.zip)
        elif args.command == "smoke": result = browser_smoke(args.zip)
        else: result = {"extracted_to": str(extract_verified_zip(args.zip, args.out_dir)), "final_authority": "NOT_ADMITTED"}
        print(json.dumps(result, indent=2, sort_keys=True)); return 0
    except PreviewParseError as exc:
        print(json.dumps({"status": "DENIED", "deny_code": exc.code, "final_authority": "NOT_ADMITTED"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
