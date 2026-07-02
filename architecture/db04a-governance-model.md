# DB-04A Governance Model

Full doc: https://app.notion.com/p/38be5a7ff397816bbdfaecca97ed66df
Status: PASS WITH OPEN ADRs

## Core Rules
- Notion Valid != Canonical Approved
- source string != source_claim
- Pipeline QA != Human Review
- Imported=true != CANONICAL_APPROVED_EXPORT
- VR-07: Project B may not consume raw Staging rows in client runtime

## ADR Status (closed via DB-05, 2026-07-01)
- ADR-04A-001: CLOSED -- accept DB-04A entity naming
- ADR-04A-002: CLOSED -- Wiki_ Notes = intake records only
- ADR-04A-003: CLOSED -- dosha_relevance = interpretive, not biomedical
- ADR-04A-004: CLOSED -- runtime needs resolved claim or labeled INTERNAL_PRACTICE
- ADR-04A-005: CLOSED -- protocol_id globally unique, slug namespace format
- ADR-04A-006: OPEN -- before production
- ADR-04A-007: OPEN -- before DDL
- ADR-04A-008: CLOSED -- ABSOLUTE contraindications require external reviewer
