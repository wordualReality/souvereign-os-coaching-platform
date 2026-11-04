# Step 10 / C08-B01 synthetic consumer handoff delta

Status: `DRAFT / SYNTHETIC_TEST_ONLY / PREVIEW_ONLY / NON_EXECUTABLE / NOT_ADMITTED`. This is a deterministic local demonstrator for CAP-BL-019/021, not an accepted cross-lane API, published ProtocolVersion, botanical identification, inventory feed or personal recommendation. The invented labels, months and region codes are not real botanical facts. No ingestion, foraging, diagnosis, prescribing or treatment instruction is provided.

Run from repository root:

```text
python3 services/kdb/offline_seasonal_botanical.py tests/kdb/fixtures/c08_b01_synthetic_preview.json
```

The additive output contract is `contracts/kdb/c08_seasonal_botanical_preview.v1.schema.json`. Inputs are a caller-supplied synthetic snapshot and query; the source content SHA-256 is recomputed over UTF-8 JSON with sorted keys and compact separators. Every result contains provenance: a consistent selected record is `PINNED_UNTRUSTED` with synthetic source and current version, statement and fixture locator, rights/license snapshot, lifecycle, digest and knowledge-as-of date; an early rejection without a valid pin says `UNAVAILABLE` and does not invent one. These are untrusted fixture claims: matching a digest verifies consistency of the supplied content, not identity, external source custody, actual license, trusted revocation freshness or human review. The fixture has no live source lookup or watermark.

## Arcava-oriented consumer example, draft only

The example fixture requests synthetic ALPHA, LEAF, region `SYN-AA`, NORTH, month 4, and pins `SYN-SRC-ALPHA` / `SYN-VER-ALPHA-1` with SHA-256 `5968b56fdb04f74431ba07107652f5b6affde86bcbccdea2eb15a34b2d199abd`. The deterministic result is `PREVIEW / SYNTHETIC_TYPICAL_SEASON`, `in_typical_season=true`, typical months `[3,4,5]`, with the full pinned provenance and `TYPICAL_NOT_REALTIME_INVENTORY`. A consumer must retain the immutable version and provenance rather than treating the result as a current inventory or user's location.

Change only `query.plant_id` to `SYNTHETIC:BETA`: the result is `ABSTAIN / SPECIES_NOT_IN_PINNED_SOURCE` and still carries the ALPHA source/version, statement and evidence locator that explain the absence. It does not suggest an alternative plant. Unknown/revoked/stale/conflicting source versions, rights/purpose/tenant mismatch, ambiguous identity or lookalike, unclear synthetic license, undocumented part, missing evidence, missing hemisphere/month, conflicting seasons, untrusted approval/health claims and uncertain/disputed records yield typed abstentions. The fixture's NORTH and SOUTH month sets are independently supplied source data; the resolver never calculates a hemispheric or climate shift.

## Handoff and remaining boundaries

KDB owns the synthetic source/version/provenance interpretation and this draft preview. Arcava owns future consumer presentation and assessment context; SOV owns its separate platform responsibilities. No personal assessment data or Arcava/SOV repository changes are included. Before a real consumer can rely on a result, separate work must establish trusted source custody, identity disambiguation, license/rights and revocation freshness, evidence/claim validation, safety review, accepted cross-lane contracts and versioned human publication.

CAP-BL-020/022/023 and KDB-C08-B02/B03/B04 remain scheduled, not executed. M01 Step 10 full handover remains PARTIAL. Step 6 creator/ACL and Step 9 governance gates remain partial, as do hosted, security and production admission. This slice creates no C04/C05 decision, canonical publication, database write, provider call or n8n activation.
