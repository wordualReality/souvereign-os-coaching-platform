# Blockers and Decisions

Date: 2026-07-01

## Active Blockers
| ID | Blocker | Unblocked By |
|---|---|---|
| BLK-001 | canonical.* SQL/DDL blocked | FX-01+AT-05+DDL-01+Aydin |
| BLK-002 | VS-01 not verified | npm run validate:r1 + canonical.* ready |
| BLK-003 | Gate C not run | DB-05 done -> FX-01 -> run Gate C |
| BLK-004 | Gate D not run | After Gate C |
| BLK-005 | Remote Supabase not pushed | Local gates pass first |
| BLK-006 | Cowork GitHub App: install at github.com/apps/claude | Aydin installs |
| BLK-007 | ADR-05-013 not created | After FX-01 |

## Resolved Decisions
| ID | Decision | Date |
|---|---|---|
| DEC-001 | P01 proceeds without canonical | 2026-07-01 |
| DEC-002 | DB-05 delivered, ADRs 001-005+008 closed | 2026-07-01 |
| DEC-003 | P-015 accepted, DDL deferred, model: protocol_asset | 2026-07-01 |
| DEC-004 | Gate D ABSOLUTE requires external reviewer | 2026-07-01 |
| DEC-005 | No autonomous canonical promotion | 2026-07-01 |

## Stop Condition
Any touch of canonical.*, dev_staging.* from Project B,
getProtocolDetail() without approved canonical_ref, or Broad UI:
-> NEEDS_ALIGNMENT.md in repo root -> stop.
