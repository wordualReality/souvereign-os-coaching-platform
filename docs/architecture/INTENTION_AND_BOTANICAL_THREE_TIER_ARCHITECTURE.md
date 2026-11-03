# Intention and Botanical Capability — Three-Tier Architecture

Status: `CURRENT SCOPE ADDENDUM`
Architecture impact: `NO REOPEN`

## 1. Presentation tier

### Member experience

- pre-session intention reminder;
- intention editor or approved template selector;
- privacy and coach-sharing control;
- stage-aware language for `FOUNDATION`, `INTEGRATION` and `ADVANCED` practice;
- local botanical discovery cards with evidence grade, season, legal status, preparation, contraindication and source provenance;
- explicit unavailable, unverified, withdrawn and “do not use” states.

### Coach and tenant administration

- configure intention policy at journey, phase, unit or session level;
- curate intention templates and stage progression;
- no default access to private intention text;
- reference published botanical entries without editing Canonical evidence.

## 2. Application/service tier

Project-B-owned services:

- `IntentionPolicyService`;
- `ParticipantIntentionService`;
- `SessionReadinessService`;
- `ReminderOrchestrationService`;
- `ConsentAndVisibilityService`;
- `BotanicalDiscoveryQueryService`.

Rules:

- reminder decisions are deterministic and policy-driven;
- session readiness evaluates effective access and the active intention policy;
- free-text intention is excluded from audit/outbox payloads;
- botanical discovery is read-only against a producer-owned published projection;
- Project B cannot promote, edit or reinterpret Canonical evidence;
- incomplete identity, legal or safety status fails closed.

## 3. Data and Canonical tier

### Project-B-owned data

- `practice_intention_policy`;
- `participant_intention`;
- `session_intention_state`;
- `reminder_delivery_record`;
- `intention_visibility_consent`.

### Database/Canonical-owned data

- `botanical_taxon`;
- `botanical_occurrence_region`;
- `botanical_phenology_window`;
- `botanical_legal_status`;
- `botanical_preparation`;
- `botanical_evidence_assessment`;
- `botanical_safety_profile`;
- `botanical_interaction`;
- `botanical_publication_version`;
- `botanical_source_provenance`.

## 4. Producer-owned contract

Project B consumes a versioned `LocalBotanicalEvidenceProjection` through an approved API, restricted RPC or materialized read model. The projection contains only published entries and carries:

- canonical taxon and preparation identity;
- coarse region and season/phenology;
- legal and conservation status;
- evidence grade and source version;
- preparation-specific use boundary;
- contraindication, interaction and vulnerable-group flags;
- publication, revalidation and withdrawal state.

Project B never reads staging/candidate evidence tables and never writes Canonical evidence.

## 5. State models

### Intention policy

`DRAFT → ACTIVE → SUPERSEDED → RETIRED`

### Participant intention

`EMPTY → SET → CONFIRMED → COMPLETED_OR_EXPIRED → ARCHIVED`

### Botanical evidence

`DISCOVERED → IDENTITY_REVIEW → LEGAL_REVIEW → EVIDENCE_REVIEW → SAFETY_REVIEW → APPROVED_FOR_PUBLICATION → PUBLISHED → REVALIDATION_DUE → WITHDRAWN`

Identity, legal, evidence and safety review cannot be skipped.

## 6. Events

- `intention.policy.activated.v1`;
- `session.intention.reminder.requested.v1`;
- `session.intention.set.v1`;
- `session.intention.visibility.changed.v1`;
- `botanical.evidence.published.v1`;
- `botanical.evidence.revalidation_due.v1`;
- `botanical.evidence.withdrawn.v1`.

## 7. Cross-lane ownership

- Project B owns session UX, intention policy/runtime, reminders, consent and local discovery presentation.
- Database/Canonical owns botanical identity, occurrence source, evidence, safety, legal status, publication and withdrawal semantics.
- Shared Database Control owns ordered migration, RLS, audit/outbox and cross-schema controls.
- n8n may support bounded reminders or revalidation only through approved events/RPCs; it is not evidence or publication authority.

## 8. Quality and failure cases

Mandatory tests later include:

- missing intention under each policy mode;
- reminder snooze/disable and duplicate delivery;
- private intention hidden from coach and logs;
- cross-tenant access denial;
- stale or withdrawn botanical projection;
- protected species location suppression;
- preparation mismatch and dosage-transfer denial;
- incomplete interaction/safety review fail-closed;
- offline/stale seasonality disclosure;
- audit reconstruction without sensitive text leakage.
