# ARC-P16 — SOV-priority producer-contract physicalization

## Scope
Bounded ARC10-T010 physicalization only. No runtime producer, database, provider, SOV or KDB mutation.

## Physicalized contracts
- CT-ARC-002 PublishedJourneyVersionProjection, E08, runtime backing still ARC10-T050.
- CT-ARC-003 EnrollmentExecutionProjection, E09, runtime backing still ARC10-T050.
- CT-ARC-004 JourneyExecutionCorrelation, E08, runtime backing still ARC10-T050.
- CT-ARC-R03-REM-001 ReminderDue/current-intent, E10, runtime backing still ARC10-T060 and provider admission remains separate.

## Common envelope boundary
QueryEnvelope, ResponseEnvelope and EventEnvelope are abstract-only reusable Draft 2020-12 components. Direct standalone validation is forbidden; concrete contract schemas close profile-specific payloads and reject unknown authority-bearing fields. CommandEnvelope remains later ARC10-T010 scope.

## Cross-lane effect
This package may establish PHYSICAL_SCHEMA_PRESENT_AND_CHECKSUMMED only after canonical CPython 3.12.14 evidence passes. It does not establish RUNTIME_PRODUCER_READY. SOV T17/T12 must be re-read after canonical gate; no SOV mutation occurs here.

## Invariants
- 86 = 47 P0 + 39 P1.
- Food Scan × Dosha AI = DEFERRED.
- No Requirement 87, ARC-SEM-02, XLM rerun or controller restart.
- No commit/push/PR/SQL/migration/deployment.
