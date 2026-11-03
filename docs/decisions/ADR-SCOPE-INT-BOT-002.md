# ADR-SCOPE-INT-BOT-002 — Botanical Supplement Scope Boundary

Status: `ACCEPTED CLARIFICATION`
Date: 2026-08-02
Supersedes: no architecture; clarifies ambiguous use of the word `supplement` in ADR-SCOPE-INT-BOT-001 and related addenda.

## Context

The locality- and season-aware capability is built around plant taxonomy, regional occurrence, phenology, plant parts and botanical preparations. The generic term `supplement` can also include vitamins, minerals, amino acids, probiotics and synthetic substances for which locality and seasonality are not meaningful product dimensions.

## Decision

1. The currently accepted curated pilot covers **herbs, botanicals and plant-derived/botanical supplements only**.
2. `Botanical supplement` means a reviewed preparation derived from an identified botanical taxon and plant part, with preparation-specific evidence and safety data.
3. Non-botanical supplements — including vitamins, minerals, amino acids, probiotics and synthetic compounds — are outside `SCOPE-CHANGE-INT-BOT-01` and require a separate future requirements, evidence and safety domain.
4. No locality or seasonality ranking may be applied to a non-botanical supplement merely because it is commercially available in a user's region.
5. Existing safety, provenance, human-review, no-personalized-dosage and fail-closed rules remain unchanged.

## Consequences

- Current Project-B and Canonical models remain coherent and taxon-based.
- The term `botanical/supplement` in prior documents is interpreted as `botanical and botanical-supplement` for the current pilot.
- A future broad supplement register requires its own owner return, data model, jurisdictional controls and ADR.

## Gate impact

This clarification does not block FPS-00C local validation and does not authorize implementation.