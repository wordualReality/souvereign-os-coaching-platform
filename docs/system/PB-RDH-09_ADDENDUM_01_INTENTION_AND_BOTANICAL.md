# PB-RDH-09 Addendum 01 — Intention Progression and Local Botanical/Supplement Register

Date: 2026-08-02
Status: `CONTROLLED SYSTEM-DOCUMENTATION ADDENDUM`
Parent baseline: `PB-RDH-09_PROJECT_B_COMPLETE_ENTERPRISE_SYSTEM_DOCUMENTATION_RC1`

This addendum is part of the current Project-B system documentation and supersedes no accepted PB-RDH-09 architecture. It records a scope extension within existing boundaries.

## Added capability

1. Intention policy per journey unit/session, pre-session reminder, private intention capture and a `FOUNDATION → INTEGRATION → ADVANCED` practice progression.
2. A locality- and season-aware botanical/supplement evidence register owned by Database/Canonical and consumed read-only by Project B.

## Architecture position

- Presentation: intention/reminder/privacy UI and read-only local botanical discovery.
- Application: deterministic session-readiness/reminder services and published-evidence query service.
- Data/Canonical: Project-B intention state; Canonical botanical taxonomy, occurrence, phenology, legal status, preparation, evidence, safety, interaction, provenance and publication state.

## Release boundary

- Intention joins the bounded MVP.
- Botanical/supplement discovery is limited to a later curated read-only pilot with 5–20 human-reviewed entries.
- No autonomous publication, individualized dosage, exact protected-species locations or unreviewed foraging instructions.

## Controlled sources

- Drive addendum: `https://docs.google.com/document/d/1Ecl-jsGoCZxrSSIY0uFgcqwDaP7LmuWZzzOoey3PlfU/edit`
- Requirements: `docs/requirements/INTENTION_AND_BOTANICAL_SCOPE_ADDENDUM.md`
- Architecture: `docs/architecture/INTENTION_AND_BOTANICAL_THREE_TIER_ARCHITECTURE.md`
- Safety: `docs/security/BOTANICAL_SAFETY_AND_LOCATION_PRIVACY_RULES.md`
- Decision: `docs/decisions/ADR-SCOPE-INT-BOT-001.md`

Implementation remains blocked until FPS-00C is validated and a successor packet explicitly authorizes the relevant work.
