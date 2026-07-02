# DB-05 CanonicalRef / Validation / Consumption Model

Full doc: https://app.notion.com/p/390e5a7ff39781399ff6ec6aedfd647c
Status: PASS WITH OPEN ADRs | Date: 2026-07-01

## Core
canonical_ref = validated reference envelope
canonical_ref != canonical truth object
canonical_ref != raw intake candidate

## Promotion Path
dev_staging.protocol_candidate
-> canonical_intake_record -> protocol_candidate -> source/contraindication candidates
-> Gate C (Source Resolution) -> Gate D (Safety Review)
-> canonical_promotion_candidate -> canonical_ref -> projection -> consumer

## Promotion Trigger
Manually by Aydin/operator. No autonomous Claude/n8n/Project B promotion.

## P01 Dependency
P01 does NOT require canonical_ref. P01 is fully decoupled.

## P-015 Video
ACCEPTED as product requirement. DDL DEFERRED.
Model: protocol_asset/content_asset relation. NOT flat field on canonical.protocol.
Follow-up: ADR-05-013 required.

## Next After DB-05
FX-01 Fixture Pack -> AT-05 Acceptance Tests -> DDL-01 -> Aydin approval
