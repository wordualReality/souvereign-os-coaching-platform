# PB-RDH-09 Release Manifest Addendum 01

Date: 2026-08-02
Status: `CURRENT ADDENDUM MANIFEST / PARENT RC1 IMMUTABLE`
Parent release: `PB-RDH-09_PROJECT_B_COMPLETE_ENTERPRISE_SYSTEM_DOCUMENTATION_RC1`

## Release rule

The original PB-RDH-09 RC1 PDF, DOCX, release manifest and SHA-256 file remain immutable historical release artifacts. This addendum extends the current documentation baseline without rewriting or invalidating their original hashes.

## Added controlled artifacts

- Drive: `PB-SCOPE-INTENTION-BOTANICAL-01 — Intention Progression and Local Botanical Supplement Register v1.0 — 2026-08-02`
  - `https://docs.google.com/document/d/1Ecl-jsGoCZxrSSIY0uFgcqwDaP7LmuWZzzOoey3PlfU/edit`
- Repository: `docs/system/PB-RDH-09_ADDENDUM_01_INTENTION_AND_BOTANICAL.md`
- Requirements: `docs/requirements/INTENTION_AND_BOTANICAL_SCOPE_ADDENDUM.md`
- Architecture: `docs/architecture/INTENTION_AND_BOTANICAL_THREE_TIER_ARCHITECTURE.md`
- Safety: `docs/security/BOTANICAL_SAFETY_AND_LOCATION_PRIVACY_RULES.md`
- Decisions: `docs/decisions/ADR-SCOPE-INT-BOT-001.md` and `ADR-SCOPE-INT-BOT-002.md`
- Traceability: `docs/traceability/IMPLEMENTATION_TRACEABILITY_INDEX.md`
- Cursor control: `.cursor/rules/45-intention-botanical-safety.mdc`

## Scope status

- Intention policy, pre-session reminder, private intention capture and staged practice progression: accepted for the bounded MVP, implementation not yet authorized.
- Local botanical and botanical-supplement register: accepted for architecture and requirements as a later curated read-only pilot.
- Non-botanical supplements: outside this addendum and require a separate future capability.

## Open controls

- FPS-00C local validation and Cursor-rule recognition remain mandatory before merge.
- Database/Canonical owner return remains mandatory before botanical schema or publication-contract implementation.
- Notion mirror remains pending while the connector is unavailable.

## Gate

`PASS_WITH_LOCAL_EXECUTION_REQUIRED`

No feature, SQL, workflow, deployment or production authority is created by this manifest addendum.