# Whole-System Review Checklist

Use this checklist in addition to packet-specific Definition of Ready/Done and quality gates.

## Purpose and outcome

- [ ] The packet names the whole-system purpose it supports.
- [ ] Success is defined as an observable system outcome, not only a component output.
- [ ] Local optimization cannot undermine tenant safety, provenance, privacy, operability or another owner lane.

## Interactions and ownership

- [ ] Upstream and downstream systems are named.
- [ ] Producer, consumer, owner and contract are explicit for every cross-system interaction.
- [ ] No owner boundary is bypassed through direct tables, hidden coupling or duplicated truth.
- [ ] Failure ownership and escalation are explicit.

## Feedback loops

- [ ] Inputs/signals, processing, decision, action and resulting feedback are mapped.
- [ ] Each signal has purpose, source, freshness, quality, retention and permitted-use rules.
- [ ] Human review is retained where safety, rights, canonical promotion or high-impact adaptation requires it.
- [ ] Stale, missing, contradictory or delayed feedback has a fail-safe behavior.

## Failure and resilience

- [ ] Blast radius across tenants, roles, data classes and workflows is assessed.
- [ ] Upstream failure, downstream failure, timeout, retry, duplicate, partial completion and stale-state cases are tested where relevant.
- [ ] Audit/outbox/traces/evidence can reconstruct the interaction.
- [ ] Rollback, containment and recovery ownership are defined.

## Learning and adaptation

- [ ] Executed evidence is fed into the next decision without silently changing accepted authority.
- [ ] Lessons learned distinguish design defect, implementation defect, environment defect and process defect.
- [ ] Exactly one successor addresses the highest-value authorized dependency or repair.

## Gate rule

A packet cannot receive `PASS` when its local behavior is correct but a material whole-system interaction, feedback loop, ownership boundary or failure propagation remains untested. Use `PASS_WITH_BLOCKERS`, `REPAIR_REQUIRED` or `BLOCKED` as appropriate.
