# System-Level Acceptance Gates

Status: CURRENT GOVERNANCE CONTROL

These gates supplement packet-specific acceptance criteria. A component may pass its local tests and still fail the system gate.

## SLG-01 Purpose and outcome

- Whole-system purpose and stakeholder outcome are named.
- Success is observable beyond file creation or component output.
- The change does not optimize engagement, throughput or autonomy against user benefit, safety or governance.

## SLG-02 Boundaries and interactions

- Upstream/downstream systems, owners, producers, consumers and contracts are explicit.
- No duplicated truth, direct-table bypass or hidden cross-lane coupling is introduced.
- Cross-lane impact matrix is completed for material changes.

## SLG-03 Feedback quality

- Signal source, timing, freshness, quality, retention and permitted use are defined.
- Missing, stale, duplicate, delayed and contradictory feedback has a tested behavior.
- Human agency/review is preserved where required.

## SLG-04 Failure propagation and resilience

- Blast radius across tenants, roles, data classes and workflows is assessed.
- Relevant upstream/downstream failure, timeout, retry, duplicate, partial completion and recovery cases are tested.
- Audit/outbox/traces/evidence can reconstruct material interactions.

## SLG-05 Security, privacy and provenance

- Effective access fails closed.
- Cross-tenant and unauthorized negative tests pass.
- Raw candidates, secrets and personal data do not leak through interfaces or evidence.
- Canonical rights, provenance, review and withdrawal semantics are preserved.

## SLG-06 Operability and learning

- A named owner can detect, diagnose, contain, recover and learn from failure.
- Metrics/logs/traces/runbook requirements are appropriate to scope.
- Lessons learned produce one evidence-based successor without silently changing authority.

## Gate decision

- `PASS`: all applicable local and system-level criteria are evidenced.
- `PASS_WITH_BLOCKERS`: bounded result is accepted but named system-level evidence or downstream capability remains blocked.
- `REPAIR_REQUIRED`: defects can be repaired in one bounded successor.
- `BLOCKED`: authority, owner, source, environment or critical interaction evidence is missing.
- `FAILED`: unsafe or unacceptable systemic behavior was produced.

A locally passing component cannot receive `PASS` while a material system interaction or failure path remains unverified.
