# Content 3-Layer Architecture

Date: 2026-07-01

## Layers
Layer 1 -- Notion: Tags DB, Notes DB (27 candidates Gate A+B PASS), Staging DB, n8n Pipelines A+B
Layer 2 -- Canonical DB: canonical.protocol/.source/.source_claim/.canonical_ref -- NOT IMPLEMENTED
Layer 3 -- Project B: consumes approved projections via canonical_ref/getProtocolDetail()

## Core Principle
Notion produces candidates. Canonical DB produces approved truth. Project B consumes approved truth.

## Gate Status
| Gate | Status |
|---|---|
| A Syntax | PASS (all 27) |
| B Pipeline QA | PASS (all 27) |
| C Source Resolution | DEFINED, NOT RUN |
| D Safety Review | DEFINED, NOT RUN |
| E Canonical Promotion | BLOCKED |
