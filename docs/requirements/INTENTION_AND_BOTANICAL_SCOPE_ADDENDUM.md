# Intention Progression and Local Botanical/Supplement Scope Addendum

Status: `ACCEPTED_FOR_REQUIREMENTS_AND_ARCHITECTURE`
Architecture impact: `EXTENSION_WITHIN_EXISTING_BOUNDARIES / NO REOPEN`
Implementation authority: none until the current governance gate passes and a successor packet authorizes implementation.

## Capability A — Intention and progressive practice

- `INT-FR-001`: configure an intention policy per journey, phase, unit or session.
- `INT-FR-002`: support `OPTIONAL`, `PROMPTED`, `REQUIRED_BEFORE_START` and `ADVANCED_NON_INSTRUMENTAL` modes.
- `INT-FR-003`: issue a configurable pre-session reminder when policy requires an intention and none is active.
- `INT-FR-004`: let the member enter free text, select an approved template, keep it private, skip where permitted, snooze or disable optional reminders.
- `INT-FR-005`: intention text is private by default; coach visibility requires explicit consent and tenant policy.
- `INT-FR-006`: store intention history separately from completion, reflection and outcome claims.
- `INT-FR-007`: support `FOUNDATION`, `INTEGRATION` and `ADVANCED` practice stages.
- `INT-FR-008`: advanced mode may use non-instrumental prompts such as “the practice is the goal” or “breathing for the sake of breathing” without performance scoring.
- `INT-FR-009`: approved product language is attention regulation, deliberate practice, self-observation and intention setting; do not claim mind control.
- `INT-FR-010`: reminder and state events must not copy sensitive free-text intention into logs or outbox payloads.

## Capability B — local botanical and supplement evidence register

- `BOT-FR-001`: use coarse locality by default; exact location is optional and separately consented.
- `BOT-FR-002`: separate occurrence, season/phenology, legal collection status, commercial availability, evidence and safe-use information.
- `BOT-FR-003`: every entry has scientific taxon, synonyms, plant part, preparation and evidence version.
- `BOT-FR-004`: occurrence must be source-attributed and confidence-rated; occurrence never implies edibility, efficacy, collectability or safety.
- `BOT-FR-005`: never expose exact coordinates for protected, threatened, sensitive or private-location species.
- `BOT-FR-006`: “where to find” is limited to region/habitat, lawful public locations or verified retail channels.
- `BOT-FR-007`: preparation and intake instructions are shown only for the exact reviewed preparation; do not transfer dosage across plant parts, extracts or concentrations.
- `BOT-FR-008`: include contraindications, interactions, vulnerable-group restrictions, contamination/adulteration risk and stop conditions.
- `BOT-FR-009`: publication requires authorized human review.
- `BOT-FR-010`: no personalized recommendation when identity, legal status, evidence, interaction screening or safety review is incomplete.
- `BOT-FR-011`: first release is a curated read-only pilot with 5–20 reviewed entries; autonomous ingestion, exact foraging maps and individualized dosing are non-goals.
- `BOT-FR-012`: user reports create review candidates, never automatic truth updates.

## Evidence classes

- `A`: regulator or public-health monograph/assessment.
- `B`: systematic review/meta-analysis or replicated controlled evidence.
- `C`: limited clinical evidence or documented traditional use.
- `D`: insufficient, conflicting or indirect evidence.
- `X`: safety concern, prohibited/restricted use or no recommendation.

## MVP decision

The intention policy, reminder and private intention capture join the bounded MVP. The botanical/supplement capability is specified now but may only enter as a later curated read-only pilot after effective access, database ownership and publication contracts are proven.

## Source

Controlled Drive addendum:
`https://docs.google.com/document/d/1Ecl-jsGoCZxrSSIY0uFgcqwDaP7LmuWZzzOoey3PlfU/edit`
