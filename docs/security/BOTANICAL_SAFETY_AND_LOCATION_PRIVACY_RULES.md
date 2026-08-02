# Botanical Safety and Location Privacy Rules

Status: `CURRENT SAFETY CONTROL`

## Location privacy

- Coarse locality is the default: country, region, municipality or postal-code centroid.
- Exact location is optional, separately consented, purpose-limited and revocable.
- Exact coordinates for protected, threatened, sensitive or private-location species are never exposed.
- Location data is not copied into general logs, analytics or outbox payloads.
- Retention must be explicit and minimal; a user can clear stored locality.

## Identity and occurrence

- Scientific taxon identity and plant part are mandatory.
- Image recognition or a single crowd-sourced observation is insufficient for ingestion advice.
- Occurrence confidence, observation date and source must be shown separately from health evidence.
- Local occurrence does not imply legal collection, edibility, efficacy or safety.

## Evidence and preparation

- Use instructions must match the reviewed species, plant part, preparation, concentration and route.
- Never transfer a dose or preparation instruction across extracts, teas, powders, tinctures, oils or supplements.
- Official monographs and public-health assessments outrank secondary summaries.
- Traditional use is labeled separately from demonstrated clinical effect.
- Conflicting, insufficient or outdated evidence results in `NO_RECOMMENDATION` or `REVIEW_REQUIRED`.

## Safety screen

Before any personalized recommendation, the system must know or explicitly decline to assess:

- age and vulnerable-group status;
- pregnancy or breastfeeding;
- allergies;
- chronic conditions;
- current medicines and relevant supplements;
- surgery or acute illness context;
- preparation and intended duration.

Missing critical information fails closed. The curated pilot does not perform individualized dosing.

## Collection and conservation

- Display legal status and conservation status for the user jurisdiction.
- Do not direct users into protected areas, private property, contaminated sites, roadsides or unsafe habitats.
- Do not reveal exact sites for protected/threatened species.
- Collection guidance requires current jurisdiction review; otherwise show observation-only or retail-only status.

## Publication and incident control

- Human review is mandatory before publication.
- Every entry has evidence version, reviewer, review date and revalidation date.
- Adverse-effect or misidentification reports create an incident/review candidate.
- Withdrawal propagates to all consuming applications through a versioned event or projection state.

## Claims boundary

Do not claim diagnosis, treatment, prevention, cure, guaranteed benefit, medical equivalence or suitability for a specific user unless an authorized clinical/regulatory path explicitly permits it. “Natural”, “local” and “traditional” are not safety or efficacy claims.
