# ADR-SCOPE-INT-BOT-001 — Intention Progression and Local Botanical/Supplement Register

Status: `ACCEPTED_FOR_ARCHITECTURE_AND_REQUIREMENTS`
Date: 2026-08-02

## Context

The product requires an intention-setting mechanism before sessions and a progressive practice model that moves from explicit intention and attention regulation toward advanced non-instrumental practice. It also requires a locality- and season-aware register for herbs, botanicals and supplements with scientific, phytological, legal and safety evidence.

## Decision

1. Add intention policy, reminder, private intention capture and stage progression to the Project-B bounded MVP.
2. Model botanical/supplement evidence as a Database/Canonical-owned domain consumed by Project B through a published read-only projection.
3. Limit the first botanical release to a curated human-reviewed pilot with 5–20 entries.
4. Prohibit autonomous publication, exact protected-species locations, unreviewed foraging instructions, generic dosage transfer and personalized dosage in the pilot.
5. Preserve the existing three-tier architecture, bounded contexts, owner lanes, RLS, audit/outbox and evidence gates.

## Rationale

The intention capability is directly coupled to session readiness and journey delivery, so Project B owns its runtime and UX. Botanical identity, evidence, safety, legal status and publication are shared knowledge concerns requiring Canonical ownership and human review. This avoids duplicating or weakening evidence truth inside the product application.

## Consequences

- The architecture remains frozen; this is an extension within existing boundaries.
- Project B requires new requirements, state and reminder contracts.
- Database/Canonical requires a separate owner return for schema and publication contract.
- The current FPS-00C validation gate remains the only executable action.
- Notion alignment remains pending connector recovery; Drive and Git are current control sources.

## Sources

- Controlled addendum: `https://docs.google.com/document/d/1Ecl-jsGoCZxrSSIY0uFgcqwDaP7LmuWZzzOoey3PlfU/edit`
- Shared alignment register: `https://docs.google.com/document/d/1AYXt0qswYMgCBKB_VZzKea03OsRrF2jQCG0Ld2tlUrw/edit`
