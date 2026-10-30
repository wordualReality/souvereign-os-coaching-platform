"""Portable offline review demo pack. Not a hosted website.

Packages current P16 workbench HTML and P17 snapshot-delta HTML into a local
file bundle with a landing page, checksum manifest, and README. Snapshot order
is caller-supplied and UNATTESTED. The pack is SNAPSHOT_UNTRUSTED, NON_EXECUTABLE,
NOT_ASSIGNED, and NOT_ADMITTED. It is not a reviewer UI, C04 case, or evidence export.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Mapping

from offline_review_case_detail import UUID_RE
from offline_review_inbox import MAX_CHARS, parse_inbox_json
from offline_review_snapshot_delta import PACKET as DELTA_PACKET, snapshot_delta
from offline_review_workbench import (
    BANNER,
    GATES,
    PACKET as WORKBENCH_PACKET,
    _assert_redacted,
    _denied_page,
    _dt,
    _shell,
    _t,
    workbench,
)
from review_handoff_preview import (
    ATC10_NAMED_CANDIDATES,
    PACKET as PREVIEW_PACKET,
    REPAIR_PACKET,
    PreviewParseError,
    REPO_ROOT,
    _safe_local_file,
    bound_commit,
)

PACKET = "KDB-M01-P18-PORTABLE-OFFLINE-REVIEW-DEMO-PACK-01"
FIXED_FILES = ("index.html", "current.html", "changes.html", "manifest.json", "README.txt")
DIR_NAME_RE = r"^[A-Za-z0-9._-]{1,64}$"
DEMO_ROOT = REPO_ROOT / "tests" / "kdb" / "demo-artifacts"
CHANGE_LABELS = "POSSIBLE_CHANGE_ONLY SNAPSHOT_ORDER_NOT_ATTESTED EVENT_WATERMARK_UNKNOWN"
NAV = (
    '<nav aria-label="Demo">\n'
    "<p>"
    '<a href="index.html">Uebersicht</a> '
    '<a href="current.html">Aktuelle Faelle</a> '
    '<a href="changes.html">Aenderungen</a>'
    "</p>\n"
    "</nav>\n"
)


def _deny_parse(code: str) -> None:
    raise PreviewParseError(code)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _with_nav(page: str) -> str:
    marker = "<main>\n"
    if page.count(marker) != 1:
        _deny_parse("PREVIEW_LEAK")
    return page.replace(marker, marker + NAV, 1)


def _zero_counts() -> dict[str, int]:
    return {
        "baseline_eligible_count": 0,
        "current_eligible_count": 0,
        "visible_current_count": 0,
        "added_count": 0,
        "removed_or_denied_count": 0,
        "unchanged_count": 0,
    }


def _counts_from_delta(delta: Mapping[str, Any]) -> dict[str, int]:
    if delta.get("delta_status") == "DELTA_DENIED":
        return _zero_counts()
    return {
        "baseline_eligible_count": int(delta.get("baseline_eligible_count") or 0),
        "current_eligible_count": int(delta.get("current_eligible_count") or 0),
        "visible_current_count": int(delta.get("visible_current_count") or 0),
        "added_count": int(delta.get("added_count") or 0),
        "removed_or_denied_count": int(delta.get("removed_or_denied_count") or 0),
        "unchanged_count": int(delta.get("unchanged_count") or 0),
    }


def _current_ids(html_page: str) -> list[str]:
    found = re.findall(r'id="case-([0-9a-fA-F-]{36})"', html_page)
    ids: list[str] = []
    for item in found:
        if re.fullmatch(UUID_RE, item) is None:
            _deny_parse("PREVIEW_LEAK")
        ids.append(item.lower())
    return ids


def _counts_dl(counts: Mapping[str, int]) -> str:
    return (
        "<dl>\n"
        + _dt("BASELINE_ELIGIBLE_COUNT", counts["baseline_eligible_count"])
        + _dt("CURRENT_ELIGIBLE_COUNT", counts["current_eligible_count"])
        + _dt("VISIBLE_CURRENT_COUNT", counts["visible_current_count"])
        + _dt("ADDED_COUNT", counts["added_count"])
        + _dt("REMOVED_OR_DENIED_COUNT", counts["removed_or_denied_count"])
        + _dt("UNCHANGED_COUNT", counts["unchanged_count"])
        + "</dl>\n"
    )


def _index_page(
    *,
    denied: bool,
    deny_code: str | None,
    counts: Mapping[str, int],
    current_ids: list[str],
    commit: str,
) -> str:
    case_block = ""
    if denied:
        case_block = (
            "<p>DEMO_DENIED</p>\n"
            f"<p>deny_code {_t(deny_code or 'DELTA_DENIED')}</p>\n"
            "<p>Keine Fallseiten.</p>\n"
        )
    elif current_ids:
        items = []
        for work_id in current_ids:
            items.append(
                f'<li><a href="current.html#case-{_t(work_id)}">{_t(work_id)}</a></li>\n'
            )
        case_block = "<h2>Aktuelle Faelle</h2>\n<ul>\n" + "".join(items) + "</ul>\n"
    else:
        case_block = "<p>Keine aktuellen Faelle.</p>\n"
    body = (
        "<h1>KDB Review Demo. Synthetische Vorschau</h1>\n"
        f"<p>source_commit {_t(commit)} LABEL_NOT_ATTESTED</p>\n"
        f"<p>{_t(CHANGE_LABELS)}</p>\n"
        "<p>Die Snapshot-Reihenfolge ist eine Eingabe. Sie ist keine belegte Ereignisfolge.</p>\n"
        "<p>Keine Review-Zuweisung. Keine C04-Entscheidung. Keine Veroeffentlichung.</p>\n"
        + _counts_dl(counts)
        + case_block
        + "<p>"
        '<a href="current.html">Aktuelle Faelle</a> '
        '<a href="changes.html">Aenderungen</a>'
        "</p>\n"
    )
    page = _shell("KDB Review Demo. Synthetische Vorschau", body)
    return _with_nav(page)


def _readme(counts: Mapping[str, int], *, commit: str, pack_status: str) -> str:
    lines = [
        "KDB Offline Review Demo. Synthetische Vorschau.",
        "",
        BANNER,
        GATES,
        CHANGE_LABELS,
        "LOCAL_FILE_INTEGRITY_ONLY",
        "NOT_AUTHORITATIVE_PROVENANCE",
        "LABEL_NOT_ATTESTED",
        pack_status,
        "",
        "Oeffnen Sie index.html als lokale Datei. Es wird kein Server benoetigt.",
        "Keine Review-Zuweisung. Keine C04-Entscheidung. Keine Veroeffentlichung.",
        "Die Snapshot-Reihenfolge ist eine Eingabe. Sie ist keine belegte Ereignisfolge.",
        "Pruefsummen gelten nur fuer diese lokalen Dateien.",
        "",
        "Dateien",
        "index.html",
        "current.html",
        "changes.html",
        "manifest.json",
        "README.txt",
        "",
        f"BASELINE_ELIGIBLE_COUNT {counts['baseline_eligible_count']}",
        f"CURRENT_ELIGIBLE_COUNT {counts['current_eligible_count']}",
        f"VISIBLE_CURRENT_COUNT {counts['visible_current_count']}",
        f"ADDED_COUNT {counts['added_count']}",
        f"REMOVED_OR_DENIED_COUNT {counts['removed_or_denied_count']}",
        f"UNCHANGED_COUNT {counts['unchanged_count']}",
        f"source_commit {commit} LABEL_NOT_ATTESTED",
        "",
    ]
    return "\n".join(lines)


def _manifest(
    *,
    pack_status: str,
    deny_code: str | None,
    counts: Mapping[str, int],
    file_sha256: Mapping[str, str],
    commit: str,
) -> dict[str, Any]:
    return {
        "packet": PACKET,
        "workbench_packet": WORKBENCH_PACKET,
        "delta_packet": DELTA_PACKET,
        "preview_packet": PREVIEW_PACKET,
        "repair_packet": REPAIR_PACKET,
        "df_adoption": "DF-20261029-01",
        "pack_status": pack_status,
        "deny_code": deny_code,
        "integrity": "LOCAL_FILE_INTEGRITY_ONLY",
        "provenance": "NOT_AUTHORITATIVE_PROVENANCE",
        "source_commit_attestation": "LABEL_NOT_ATTESTED",
        "snapshot_authority": "SNAPSHOT_UNTRUSTED",
        "snapshot_order": "SNAPSHOT_ORDER_NOT_ATTESTED",
        "change_authority": "POSSIBLE_CHANGE_ONLY",
        "event_watermark": "EVENT_WATERMARK_UNKNOWN",
        "assignment": "NOT_ASSIGNED",
        "publication": "NOT_PUBLISHED",
        "final_authority": "NOT_ADMITTED",
        "execution": "NON_EXECUTABLE",
        "db_write": "NOT_ADMITTED",
        "c04_human_decision": "NOT_WRITTEN",
        "c05_canonical_admission": "NOT_WRITTEN",
        "outbox": "NOT_EMITTED",
        "gate": "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        "hosted_verified": "HOSTED_VERIFIED_NO",
        "logical_objects_claimed": "NOT_18_OF_18",
        "inventory_source": "UNCONFIRMED_ATC10_CANDIDATES",
        "physical_sql001_tables": 12,
        "atc10_named_candidates": len(ATC10_NAMED_CANDIDATES),
        "source_commit": commit,
        "baseline_eligible_count": counts["baseline_eligible_count"],
        "current_eligible_count": counts["current_eligible_count"],
        "visible_current_count": counts["visible_current_count"],
        "added_count": counts["added_count"],
        "removed_or_denied_count": counts["removed_or_denied_count"],
        "unchanged_count": counts["unchanged_count"],
        "files": dict(file_sha256),
    }


def demo_pack(
    baseline: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    pin = bound_commit(commit)
    delta = snapshot_delta(baseline, current, commit=pin)
    current_wb = workbench(current, commit=pin)
    denied = delta.get("delta_status") == "DELTA_DENIED"
    deny_code = str(delta.get("deny_code") or "") if denied else None
    counts = _counts_from_delta(delta)
    if denied:
        current_html = _with_nav(_denied_page(deny_code or "DELTA_DENIED"))
        changes_html = _with_nav(str(delta.get("html") or ""))
        current_ids: list[str] = []
        pack_status = "DEMO_DENIED"
    else:
        current_html = _with_nav(str(current_wb.get("html") or ""))
        changes_html = _with_nav(str(delta.get("html") or ""))
        current_ids = _current_ids(current_html)
        pack_status = "PREVIEW_ONLY"
        if int(current_wb.get("card_count") or 0) != len(current_ids):
            _deny_parse("PREVIEW_LEAK")
    index_html = _index_page(
        denied=denied,
        deny_code=deny_code,
        counts=counts,
        current_ids=current_ids,
        commit=pin,
    )
    readme = _readme(counts, commit=pin, pack_status=pack_status)
    staged = {
        "index.html": index_html,
        "current.html": current_html,
        "changes.html": changes_html,
        "README.txt": readme,
    }
    file_sha256 = {name: _sha256_text(text) for name, text in staged.items()}
    manifest = _manifest(
        pack_status=pack_status,
        deny_code=deny_code,
        counts=counts,
        file_sha256=file_sha256,
        commit=pin,
    )
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    artifacts = {**staged, "manifest.json": manifest_text}
    for name in FIXED_FILES:
        _assert_redacted(artifacts[name])
        if "READY" in artifacts[name]:
            _deny_parse("PREVIEW_LEAK")
    bundle = "".join(artifacts[name] for name in FIXED_FILES)
    _assert_redacted(bundle)
    return {
        "packet": PACKET,
        "pack_status": pack_status,
        "deny_code": deny_code,
        "manifest": manifest,
        "artifacts": artifacts,
        "file_sha256": file_sha256,
        "df_adoption": "DF-20261029-01",
        "snapshot_authority": "SNAPSHOT_UNTRUSTED",
        "snapshot_order": "SNAPSHOT_ORDER_NOT_ATTESTED",
        "change_authority": "POSSIBLE_CHANGE_ONLY",
        "event_watermark": "EVENT_WATERMARK_UNKNOWN",
        "assignment": "NOT_ASSIGNED",
        "publication": "NOT_PUBLISHED",
        "final_authority": "NOT_ADMITTED",
        "execution": "NON_EXECUTABLE",
        "db_write": "NOT_ADMITTED",
        "c04_human_decision": "NOT_WRITTEN",
        "c05_canonical_admission": "NOT_WRITTEN",
        "outbox": "NOT_EMITTED",
        "gate": "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
        "hosted_verified": "HOSTED_VERIFIED_NO",
        "logical_objects_claimed": "NOT_18_OF_18",
        "inventory_source": "UNCONFIRMED_ATC10_CANDIDATES",
        "physical_sql001_tables": 12,
        "source_commit": pin,
        "source_commit_attestation": "LABEL_NOT_ATTESTED",
        "integrity": "LOCAL_FILE_INTEGRITY_ONLY",
        "provenance": "NOT_AUTHORITATIVE_PROVENANCE",
        **counts,
    }


def _load_payload(path: str | Path) -> tuple[dict[str, Any], Path]:
    location = _safe_local_file(path)
    if location.stat().st_size > MAX_CHARS:
        _deny_parse("INPUT_TOO_LARGE")
    try:
        text = location.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise PreviewParseError("INVALID_UNICODE") from exc
    return parse_inbox_json(text), location


def demo_pack_files(
    baseline_path: str | Path,
    current_path: str | Path,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    pin = bound_commit(commit)
    baseline, baseline_location = _load_payload(baseline_path)
    current, current_location = _load_payload(current_path)
    if baseline_location.resolve() == current_location.resolve():
        _deny_parse("SAME_SNAPSHOT_PATH")
    return demo_pack(baseline, current, commit=pin)


def _ensure_demo_root() -> Path:
    root = DEMO_ROOT
    if root.exists():
        if root.is_symlink() or not root.is_dir():
            _deny_parse("SYMLINK_DENIED")
        return root.resolve()
    os.mkdir(root, mode=0o700)
    return root.resolve()


def _bound_out_dir(output: str | Path) -> Path:
    text_path = str(output)
    lowered = text_path.lower()
    if lowered.startswith("http://") or lowered.startswith("https://") or lowered.startswith("file:"):
        _deny_parse("NETWORK_PATH_DENIED")
    if "\x00" in text_path:
        _deny_parse("PATH_ESCAPE_DENIED")
    location = Path(text_path)
    if location.is_absolute():
        _deny_parse("PATH_ESCAPE_DENIED")
    if ".." in location.parts:
        _deny_parse("PATH_ESCAPE_DENIED")
    if location.is_symlink():
        _deny_parse("SYMLINK_DENIED")
    root = _ensure_demo_root()
    dest = (REPO_ROOT / location).resolve()
    try:
        dest.relative_to(root)
    except ValueError:
        _deny_parse("PATH_ESCAPE_DENIED")
    if dest.parent != root:
        _deny_parse("PATH_ESCAPE_DENIED")
    if dest.parent.is_symlink():
        _deny_parse("SYMLINK_DENIED")
    if not re.fullmatch(DIR_NAME_RE, dest.name):
        _deny_parse("INVALID_OUTPUT_NAME")
    if dest.exists() or dest.is_symlink():
        _deny_parse("OUTPUT_EXISTS")
    return dest


def _write_exclusive(path: Path, text: str) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    handle = os.open(path, flags, 0o644)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def write_demo_pack(artifacts: Mapping[str, str], out_dir: str | Path) -> Path:
    dest = _bound_out_dir(out_dir)
    created = False
    try:
        os.mkdir(dest, mode=0o700)
        created = True
        for name in FIXED_FILES:
            if name not in artifacts:
                _deny_parse("MISSING_ARTIFACT")
            _write_exclusive(dest / name, artifacts[name])
    except Exception:
        if created and dest.exists() and dest.is_dir() and not dest.is_symlink():
            shutil.rmtree(dest)
        raise
    return dest
