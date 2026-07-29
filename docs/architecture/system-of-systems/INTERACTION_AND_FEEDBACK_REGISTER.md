# Interaction and Feedback Register

Status: CURRENT GOVERNANCE BASELINE / IMPLEMENTATION EVIDENCE PENDING

| Loop | Producer → Consumer | Signal or contract | Purpose | Feedback / adaptation | Owner | Fail-safe |
|---|---|---|---|---|---|---|
| PB access | Identity/tenant/config → Project B runtime | effective-access decision | allow only valid tenant/role/assignment/consent/entitlement combinations | denied/expired/changed state updates later decisions | Project B + shared access owner | deny by default |
| Journey lifecycle | Admin/coach → Project B | commands/API and state transitions | create, validate, publish, enroll and deliver immutable journey versions | completion, reflection and errors inform permitted progress and later authoring | Project B | reject invalid transitions; preserve prior published version |
| Canonical reference | Database/Canonical → Project B | validated reference envelope / versioned contract | let journeys cite governed knowledge without importing canonical ownership | withdrawal/revalidation invalidates or flags dependent use | Database/Canonical producer; Project B consumer | fail closed or present controlled unavailable state |
| Member progress | Member runtime → coach projection | completion/reflection events and projections | show assigned coach only permitted progress | coach action may influence later journey decisions through explicit commands | Project B | no cross-client/tenant visibility |
| Audit/outbox | Product services → support consumers | append-only audit and versioned outbox events | reconstruct state change and trigger approved support actions | ACK/NACK, retry and dead-letter evidence | producing domain + workflow owner | idempotent retry; no direct table shortcut |
| KDB governance | approved source/reviewer → Canonical | provenance, rights, candidate, review/publication state | create governed knowledge | usage, conflict, withdrawal and revalidation signals return to human-governed review | Database/Canonical | no autonomous promotion |
| Operational learning | runtime/CI/tests → delivery control | metrics, logs, traces, test and incident evidence | detect actual behavior and systemic effects | repair, ADR or next bounded packet | active owner lane | stop on ambiguous or unsafe evidence |
| Recursive delivery | predecessor gate → executor/reviewer | packet prompt, return, evidence and gate | produce one bounded verified increment | lessons, blockers and actual result generate one successor | Implementation Control | no self-authorization or hidden continuation |

## Feedback-signal requirements

Every new signal must declare:

- source and event time;
- owner and authorized consumers;
- business/system purpose;
- freshness and quality expectations;
- data classification and retention;
- permitted decision or adaptation;
- denied uses;
- missing, stale, duplicate and contradictory behavior;
- evidence and observability path.

## Systemic review questions

- Can this interaction create an unintended reinforcing loop?
- Can a delay or stale projection cause the wrong decision?
- Can local success transfer cost or risk to another lane?
- Can the action be reversed or contained?
- Does the feedback improve the whole-system outcome rather than only engagement or throughput?

This register is a governance baseline. Packet-specific contract and runtime evidence remains mandatory.
