package com.projectb.api.domain;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

/**
 * Pure, in-memory Arcava journey lifecycle kernel.
 * This is a non-networked development slice. Actor and KDB evidence values are
 * caller-provided fixtures, NOT PIAC authentication or KDB verification.
 * Never expose it as a producer before authoritative adapters are integrated.
 */
public final class JourneyKernel {
  public enum Role { COACH, CLIENT }
  public enum ErrorCode {
    FORBIDDEN, NOT_FOUND, INVALID, STALE_REVISION, UNPUBLISHED_CANONICAL,
    WITHDRAWN, CONSENT_REQUIRED, IDEMPOTENCY_CONFLICT
  }
  public record Actor(String tenantId, String subjectId, Role role) {
    public Actor {
      required(tenantId, "tenantId"); required(subjectId, "subjectId"); Objects.requireNonNull(role);
    }
  }
  /** The KDB receipt's SHA must be checked by a future trusted KDB adapter. */
  public record CanonicalPin(String publishedVersionRef, String receiptSha256,
                             boolean approved, boolean rightsGranted) {
    public CanonicalPin {
      required(publishedVersionRef, "publishedVersionRef");
      required(receiptSha256, "receiptSha256");
    }
  }
  public record Step(String stepId, String title, CanonicalPin canonicalPin) {
    public Step {
      required(stepId, "stepId"); required(title, "step title");
      Objects.requireNonNull(canonicalPin);
    }
  }
  public record DraftView(String tenantId, UUID draftId, String title,
                          long revision, String status, List<Step> steps) {
    public DraftView { steps = List.copyOf(steps); }
  }
  public record PublishedView(String tenantId, UUID journeyVersionId,
                              UUID sourceDraftId, long version,
                              List<Step> immutableSteps, String status) {
    public PublishedView { immutableSteps = List.copyOf(immutableSteps); }
  }
  public record AssignmentView(String tenantId, UUID assignmentId,
                               String clientId, UUID journeyVersionId,
                               String status) { }
  public static final class DomainException extends RuntimeException {
    private static final long serialVersionUID = 1L;
    public final ErrorCode code;
    public DomainException(ErrorCode code, String message) {
      super(message); this.code = code;
    }
  }

  private static final class Draft {
    final String tenantId;
    final UUID id;
    String title;
    long revision = 1;
    String status = "draft";
    List<Step> steps = List.of();
    Draft(String tenantId, UUID id, String title) {
      this.tenantId = tenantId; this.id = id; this.title = title;
    }
    DraftView view() { return new DraftView(tenantId, id, title, revision, status, steps); }
  }
  private record Replay(String fingerprint, Object result) { }
  private record RequestKey(String tenantId, String subjectId, String key) { }
  private final Map<UUID, Draft> drafts = new LinkedHashMap<>();
  private final Map<UUID, PublishedView> published = new LinkedHashMap<>();
  private final Map<UUID, AssignmentView> assignments = new LinkedHashMap<>();
  private final Map<RequestKey, Replay> replays = new HashMap<>();

  public synchronized DraftView createDraft(Actor actor, String tenantId,
                                            String title, String key) {
    coach(actor, tenantId); required(title, "title");
    String fingerprint = "create|" + tenantId + "|" + actor.subjectId + "|" + title;
    DraftView prior = replay(actor, key, fingerprint, DraftView.class);
    if (prior != null) return prior;
    Draft draft = new Draft(tenantId, UUID.randomUUID(), title);
    drafts.put(draft.id, draft);
    return remember(actor, key, fingerprint, draft.view());
  }

  public synchronized DraftView updateDraft(Actor actor, String tenantId,
                                            UUID id, long expectedRevision,
                                            String title, List<Step> steps) {
    coach(actor, tenantId);
    Draft draft = draft(tenantId, id);
    if (!"draft".equals(draft.status)) throw fail(ErrorCode.INVALID, "draft is immutable after publish");
    if (draft.revision != expectedRevision) throw fail(ErrorCode.STALE_REVISION, "expected draft revision differs");
    required(title, "title");
    Objects.requireNonNull(steps);
    if (steps.isEmpty()) throw fail(ErrorCode.INVALID, "at least one step required");
    if (steps.stream().map(Step::stepId).distinct().count() != steps.size())
      throw fail(ErrorCode.INVALID, "duplicate step identifier");
    draft.steps = List.copyOf(steps);
    draft.title = title;
    draft.revision++;
    return draft.view();
  }

  public synchronized PublishedView publish(Actor actor, String tenantId, UUID draftId,
                                            long expectedRevision, String key) {
    coach(actor, tenantId);
    Draft draft = draft(tenantId, draftId);
    String fingerprint = "publish|" + tenantId + "|" + draftId + "|" + expectedRevision;
    PublishedView prior = replay(actor, key, fingerprint, PublishedView.class);
    if (prior != null) return prior;
    if (draft.revision != expectedRevision) throw fail(ErrorCode.STALE_REVISION, "stale publish request");
    if (!"draft".equals(draft.status) || draft.steps.isEmpty())
      throw fail(ErrorCode.INVALID, "draft is not publishable");
    for (Step step : draft.steps) {
      CanonicalPin pin = step.canonicalPin();
      if (!pin.approved() || !pin.rightsGranted() ||
          !pin.receiptSha256().matches("[0-9a-f]{64}"))
        throw fail(ErrorCode.UNPUBLISHED_CANONICAL, "approved, rights-bound KDB pin required");
    }
    UUID versionId = UUID.nameUUIDFromBytes((tenantId + "/" + draftId + "/" + expectedRevision)
                                           .getBytes(StandardCharsets.UTF_8));
    PublishedView version = new PublishedView(tenantId, versionId, draftId,
                                              expectedRevision, draft.steps, "published");
    draft.status = "published";
    published.put(versionId, version);
    return remember(actor, key, fingerprint, version);
  }

  public synchronized AssignmentView assign(Actor actor, String tenantId, String clientId,
                                            UUID versionId, boolean consentVerified, String key) {
    coach(actor, tenantId); required(clientId, "clientId");
    String fingerprint = "assign|" + tenantId + "|" + clientId + "|" + versionId + "|" + consentVerified;
    AssignmentView prior = replay(actor, key, fingerprint, AssignmentView.class);
    if (prior != null) return prior;
    if (!consentVerified) throw fail(ErrorCode.CONSENT_REQUIRED, "verified client consent is required");
    PublishedView version = version(tenantId, versionId);
    if (!"published".equals(version.status())) throw fail(ErrorCode.WITHDRAWN, "journey version withdrawn");
    AssignmentView result = new AssignmentView(tenantId, UUID.randomUUID(), clientId, versionId, "active");
    assignments.put(result.assignmentId(), result);
    return remember(actor, key, fingerprint, result);
  }

  public synchronized PublishedView withdraw(Actor actor, String tenantId, UUID versionId) {
    coach(actor, tenantId);
    PublishedView prev = version(tenantId, versionId);
    PublishedView withdrawn = new PublishedView(prev.tenantId(), prev.journeyVersionId(),
                            prev.sourceDraftId(), prev.version(), prev.immutableSteps(), "revoked");
    published.put(versionId, withdrawn);
    return withdrawn;
  }

  public synchronized PublishedView readAssignedVersion(Actor actor, String tenantId,
                                                        UUID assignmentId) {
    if (!tenantId.equals(actor.tenantId())) throw fail(ErrorCode.FORBIDDEN, "tenant mismatch");
    AssignmentView a = assignments.get(assignmentId);
    if (a == null || !a.tenantId().equals(tenantId)) throw fail(ErrorCode.NOT_FOUND, "assignment not found");
    if (actor.role() != Role.CLIENT || !actor.subjectId().equals(a.clientId()))
      throw fail(ErrorCode.FORBIDDEN, "client membership mismatch");
    PublishedView v = version(tenantId, a.journeyVersionId());
    if (!"published".equals(v.status())) throw fail(ErrorCode.WITHDRAWN, "journey version withdrawn");
    return v;
  }

  private Draft draft(String tenant, UUID id) {
    Draft d = drafts.get(id);
    if (d == null || !d.tenantId.equals(tenant)) throw fail(ErrorCode.NOT_FOUND, "draft not found");
    return d;
  }
  private PublishedView version(String tenant, UUID id) {
    PublishedView v = published.get(id);
    if (v == null || !v.tenantId().equals(tenant)) throw fail(ErrorCode.NOT_FOUND, "version not found");
    return v;
  }
  private static void coach(Actor actor, String tenantId) {
    Objects.requireNonNull(actor);
    if (!tenantId.equals(actor.tenantId()) || actor.role() != Role.COACH)
      throw fail(ErrorCode.FORBIDDEN, "coach/tenant access denied");
  }
  @SuppressWarnings("unchecked")
  private <T> T replay(Actor actor, String key, String fingerprint, Class<T> resultType) {
    required(key, "idempotency key");
    Replay p = replays.get(new RequestKey(actor.tenantId(), actor.subjectId(), key));
    if (p == null) return null;
    if (!p.fingerprint().equals(fingerprint) || !resultType.isInstance(p.result()))
      throw fail(ErrorCode.IDEMPOTENCY_CONFLICT, "idempotency key used for different intent");
    return (T) p.result();
  }
  private <T> T remember(Actor actor, String key, String fingerprint, T value) {
    replays.put(new RequestKey(actor.tenantId(), actor.subjectId(), key), new Replay(fingerprint, value));
    return value;
  }
  private static void required(String value, String field) {
    if (value == null || value.isBlank()) throw fail(ErrorCode.INVALID, "required " + field);
  }
  private static DomainException fail(ErrorCode code, String message) {
    return new DomainException(code, message);
  }
}
