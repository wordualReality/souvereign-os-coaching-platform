package com.projectb.api.domain;

import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.AssignmentView;
import com.projectb.api.domain.JourneyKernel.CanonicalPin;
import com.projectb.api.domain.JourneyKernel.DraftView;
import com.projectb.api.domain.JourneyKernel.DomainException;
import com.projectb.api.domain.JourneyKernel.ErrorCode;
import com.projectb.api.domain.JourneyKernel.PublishedView;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.domain.JourneyKernel.Step;
import com.projectb.api.json.JsonMini;

/**
 * Append-only command journal for one local journey service.
 * A record is visible to the kernel only after its line is durably committed.
 * Recovery rebuilds from complete lines. A trailing partial line is uncommitted.
 * A complete but malformed interior record fails closed.
 * A client request body is never copied in as a consent authority.
 */
public final class JourneyJournal {
  public interface JournalCommit {
    void commit(Path path, String line) throws IOException;
  }
  public record Projection(String tenantId, String journeyId, String versionId, String phasesJson,
                          String contentHash, String publishedAt, String publicationState) {}
  public record EnrollmentLink(String tenantId, String clientId, String versionId,
                               String assignmentId, String enrollmentId) {}

  private static final Map<String, Object> PA05_STEP_SOURCE = Map.of(
      "schema_version", 1L, "variant", "KDB_PROTOCOL_VERSION",
      "protocol_id", "05000000-0000-4000-8000-000000000009",
      "protocol_version_id", "05000000-0000-4000-8000-000000000010",
      "owning_module_id", "05000000-0000-4000-8000-000000000013",
      "taxonomy_version_id", "05000000-0000-4000-8000-000000000014",
      "relation_ids", List.of());

  public record MessageScope(String tenantId, UUID assignmentId, UUID versionId, String stepId,
                             String coachId, String clientId) {}
  public record StepMessage(UUID id, MessageScope scope, Actor sender, String body) {}
  private record MessageRetry(Actor actor, String key) {}

  private final Map<UUID, Actor> assigningCoaches = new LinkedHashMap<>();
  private final Map<MessageRetry, StepMessage> messages = new LinkedHashMap<>();

  public enum ProgressAction { COMPLETE, SHARE, REVOKE }
  public record ProgressEvent(UUID id, MessageScope scope, ProgressAction action) {}
  public record ProgressState(UUID completionId, UUID releaseId) {}
  private record ProgressRetry(Actor client, String key) {}

  private final Map<MessageScope, ProgressState> progress = new LinkedHashMap<>();
  private final Map<ProgressRetry, ProgressEvent> progressRetries = new LinkedHashMap<>();

  public static final String MEDIA_RIGHTS = "SYNTHETIC_TEST_ONLY";
  public static final String MEDIA_USE = "EXTERNAL_NAVIGATION_ONLY";
  private static final Set<String> MEDIA_HOSTS = Set.of(
      "youtube.com", "www.youtube.com", "youtu.be", "skool.com", "www.skool.com");
  public record MediaLink(UUID mediaLinkId, long linkVersion, MessageScope scope, String ownerId,
                          String url, String title, boolean withdrawn) {}
  public record MediaLinkEvent(UUID eventId, String action, MediaLink link) {}
  private record MediaRetry(Actor actor, String key) {}

  private final Map<UUID, MediaLink> mediaLinks = new LinkedHashMap<>();
  private final Map<MessageScope, UUID> activeMedia = new LinkedHashMap<>();
  private final Map<MediaRetry, MediaLinkEvent> mediaRetries = new LinkedHashMap<>();

  private final Path path;
  private final JournalCommit sink;
  private final JourneyKernel kernel = new JourneyKernel();
  private final Map<UUID, String> draftPhases = new LinkedHashMap<>();
  private final Map<UUID, Projection> projections = new LinkedHashMap<>();
  private final Map<UUID, EnrollmentLink> enrollments = new LinkedHashMap<>();
  private final Map<UUID, String> draftOrigins = new LinkedHashMap<>();
  private final Set<UUID> c19PinHistory = new java.util.LinkedHashSet<>();
  private final Map<UUID, C19LocalReview.Receipt> reviews = new LinkedHashMap<>();
  private record ReviewRetry(String tenantId, String subjectId, String key) {}
  private final Map<ReviewRetry, C19LocalReview.Receipt> reviewRetries = new LinkedHashMap<>();

  private JourneyJournal(Path path, JournalCommit sink) {
    this.path = path;
    this.sink = sink;
  }

  public static JourneyJournal open(Path path) throws IOException {
    return open(path, DurableCommit.INSTANCE);
  }

  public static JourneyJournal open(Path path, JournalCommit commit) throws IOException {
    discardUncommittedTail(path);
    JourneyJournal journal = new JourneyJournal(path, commit);
    if (Files.exists(path) && !Files.isDirectory(path)) {
      for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
        if (line.isBlank()) continue;
        try {
          journal.apply(line);
        } catch (RuntimeException ex) {
          throw new IOException("committed journal record is not recoverable", ex);
        }
      }
    }
    return journal;
  }

  public JourneyKernel kernel() { return kernel; }

  public synchronized DraftView createDraft(Actor actor, String title, String key) throws IOException {
    return createDraft(actor, title, key, null);
  }

  public synchronized DraftView createDraft(Actor actor, String title, String key, String origin) throws IOException {
    DraftView existing = kernel.peekCreate(actor, actor.tenantId(), title, key);
    if (existing != null) return existing;
    UUID draftId = UUID.randomUUID();
    commit(command("create", actor, key)
        + ",\"title\":" + JsonMini.quote(title)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + originField(origin) + "}");
    DraftView created = kernel.peekCreate(actor, actor.tenantId(), title, key);
    if (created == null) throw new IOException("committed create was not visible");
    return created;
  }

  public synchronized DraftView updateDraft(Actor actor, UUID draftId, long expectedRevision,
                                            String title, List<Step> steps, String phasesJson) throws IOException {
    return updateDraft(actor, draftId, expectedRevision, title, steps, phasesJson, null);
  }

  public synchronized DraftView updateDraft(Actor actor, UUID draftId, long expectedRevision,
                                            String title, List<Step> steps, String phasesJson,
                                            String origin) throws IOException {
    kernel.validateUpdateDraft(actor, actor.tenantId(), draftId, expectedRevision, title, steps);
    commit(command("update", actor, null)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + ",\"expected_revision\":" + expectedRevision
        + ",\"title\":" + JsonMini.quote(title)
        + ",\"steps\":" + stepsJson(steps)
        + (phasesJson == null ? "" : ",\"phases_json\":" + JsonMini.quote(phasesJson))
        + originField(origin) + "}");
    return kernel.readDraft(actor, draftId);
  }

  public synchronized C19LocalReview.Receipt localReview(Actor actor, UUID draftId, long expectedRevision,
                                                         String key) throws IOException {
    ReviewRetry retry = new ReviewRetry(actor.tenantId(), actor.subjectId(), key);
    C19LocalReview.Receipt prior = reviewRetries.get(retry);
    if (prior != null) {
      if (!prior.draftId().equals(draftId) || prior.revision() != expectedRevision)
        throw new DomainException(ErrorCode.IDEMPOTENCY_CONFLICT, "review key already bound");
      DraftView current = kernel.readDraft(actor, draftId);
      if (current.revision() != prior.revision()
          || !prior.digest().equals(C19LocalReview.digest(current)))
        throw new DomainException(ErrorCode.STALE_REVISION, "review receipt is no longer current");
      return prior;
    }
    DraftView draft = requireC19Draft(actor, draftId, expectedRevision);
    String digest = C19LocalReview.digest(draft);
    commit(command("c19_local_review", actor, key)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + ",\"expected_revision\":" + expectedRevision
        + ",\"digest\":" + JsonMini.quote(digest)
        + ",\"test_only\":true}");
    C19LocalReview.Receipt stored = reviewRetries.get(retry);
    if (stored == null) throw new IOException("committed local review was not visible");
    return stored;
  }

  public synchronized String originOf(UUID draftId) { return draftOrigins.get(draftId); }

  public synchronized C19LocalReview.Receipt currentReview(Actor actor, UUID draftId) {
    DraftView draft = kernel.readDraft(actor, draftId);
    C19LocalReview.Receipt receipt = reviews.get(draftId);
    if (receipt == null) return null;
    if (receipt.revision() != draft.revision()) return null;
    if (!receipt.digest().equals(C19LocalReview.digest(draft))) return null;
    return receipt;
  }

  public synchronized String reviewState(Actor actor, UUID draftId) {
    if (!C19LocalReview.ORIGIN.equals(draftOrigins.get(draftId))) return C19LocalReview.STATE_NONE;
    if (currentReview(actor, draftId) != null) return C19LocalReview.STATE_ACCEPTED;
    return reviews.containsKey(draftId) ? C19LocalReview.STATE_INEFFECTIVE : C19LocalReview.STATE_NONE;
  }

  public synchronized PublishedView publish(Actor actor, UUID draftId, long expectedRevision,
                                            String key) throws IOException {
    if (c19PublishDenied(actor, draftId))
      throw new DomainException(ErrorCode.FORBIDDEN, "C19 local review is not publication");
    PublishedView existing = kernel.peekPublish(actor, actor.tenantId(), draftId, expectedRevision, key);
    if (existing != null) return existing;
    kernel.validatePublish(actor, actor.tenantId(), draftId, expectedRevision);
    UUID versionId = UUID.nameUUIDFromBytes((actor.tenantId() + "/" + draftId + "/" + expectedRevision)
        .getBytes(StandardCharsets.UTF_8));
    String phases = draftPhases.getOrDefault(draftId, "[]");
    Projection prior = projections.get(versionId);
    String publishedAt = prior == null ? Instant.now().toString() : prior.publishedAt();
    String hash = sha256(phases);
    commit(command("publish", actor, key)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + ",\"expected_revision\":" + expectedRevision
        + ",\"version_id\":" + JsonMini.quote(versionId.toString())
        + ",\"phases_json\":" + JsonMini.quote(phases)
        + ",\"content_hash\":" + JsonMini.quote(hash)
        + ",\"published_at\":" + JsonMini.quote(publishedAt) + "}");
    PublishedView published = kernel.peekPublish(actor, actor.tenantId(), draftId, expectedRevision, key);
    if (published == null) throw new IOException("committed publish was not visible");
    return published;
  }

  public synchronized AssignmentView assign(Actor actor, String clientId, UUID versionId,
                                            boolean consentVerified, String key) throws IOException {
    AssignmentView existing = kernel.peekAssign(actor, actor.tenantId(), clientId, versionId, consentVerified, key);
    if (existing != null) return existing;
    kernel.validateAssign(actor, actor.tenantId(), clientId, versionId, consentVerified);
    UUID assignmentId = UUID.randomUUID();
    String enrollmentId = UUID.nameUUIDFromBytes(("enrollment/" + assignmentId)
        .getBytes(StandardCharsets.UTF_8)).toString();
    commit(command("assign", actor, key)
        + ",\"client_id\":" + JsonMini.quote(clientId)
        + ",\"version_id\":" + JsonMini.quote(versionId.toString())
        + ",\"assignment_id\":" + JsonMini.quote(assignmentId.toString())
        + ",\"enrollment_id\":" + JsonMini.quote(enrollmentId)
        + ",\"consent_verified\":" + consentVerified + "}");
    AssignmentView assigned = kernel.peekAssign(actor, actor.tenantId(), clientId, versionId, consentVerified, key);
    if (assigned == null) throw new IOException("committed assign was not visible");
    return assigned;
  }

  public synchronized PublishedView withdraw(Actor actor, UUID versionId) throws IOException {
    PublishedView current = kernel.readPublishedForCoach(actor, versionId);
    if (!"published".equals(current.status())) return current;
    commit(command("withdraw", actor, null)
        + ",\"version_id\":" + JsonMini.quote(versionId.toString()) + "}");
    return kernel.readPublishedForCoach(actor, versionId);
  }

  public synchronized Projection projection(UUID versionId) { return projections.get(versionId); }

  public synchronized EnrollmentLink enrollment(UUID enrollmentId) { return enrollments.get(enrollmentId); }

  /** Internal read-only lookup; callers still need owner guards and full stored binding checks. */
  public synchronized AssignmentView assignmentSnapshot(UUID assignmentId) {
    return kernel.assignmentSnapshot(assignmentId);
  }

  public synchronized boolean stepPresent(Projection projection, String stepId) {
    Object parsed = JsonMini.parse(projection.phasesJson());
    if (!(parsed instanceof List<?> phases)) return false;
    for (Object phase : phases) {
      if (!(phase instanceof Map<?, ?> map)) continue;
      Object steps = map.get("steps");
      if (!(steps instanceof List<?> list)) continue;
      for (Object step : list) {
        if (step instanceof Map<?, ?> stepMap && stepId.equals(stepMap.get("step_id"))) return true;
      }
    }
    return false;
  }

  public Map<String, Object> pa05Source() { return PA05_STEP_SOURCE; }

  public synchronized Step pa05Step(PublishedView version, String stepId) {
    if (!"published".equals(version.status()))
      throw new DomainException(ErrorCode.WITHDRAWN, "journey version withdrawn");
    Step step = version.immutableSteps().stream().filter(candidate -> stepId.equals(candidate.stepId()))
        .findFirst().orElseThrow(() -> new DomainException(ErrorCode.NOT_FOUND, "assigned step not found"));
    Projection projection = projections.get(version.journeyVersionId());
    if (projection == null || !version.tenantId().equals(projection.tenantId())
        || !version.journeyVersionId().toString().equals(projection.versionId())
        || !"PUBLISHED".equals(projection.publicationState())
        || !PA05_STEP_SOURCE.equals(stepSource(projection, stepId)))
      throw new DomainException(ErrorCode.UNPUBLISHED_CANONICAL, "step source does not match the PA05 fixture");
    return step;
  }

  public synchronized MessageScope messageScope(Actor actor, String clientId, UUID assignmentId,
                                                UUID versionId, String stepId) {
    AssignmentView assignment = kernel.assignmentSnapshot(assignmentId);
    if (assignment == null || !actor.tenantId().equals(assignment.tenantId())
        || !clientId.equals(assignment.clientId()) || !versionId.equals(assignment.journeyVersionId()))
      throw new DomainException(ErrorCode.NOT_FOUND, "assigned version not found");
    Actor coach = assigningCoaches.get(assignmentId);
    if (coach == null || !actor.tenantId().equals(coach.tenantId())
        || !(actor.equals(coach) || (actor.role() == Role.CLIENT && actor.subjectId().equals(clientId))))
      throw new DomainException(ErrorCode.FORBIDDEN, "assignment participant required");
    PublishedView version = actor.role() == Role.COACH
        ? kernel.readPublishedForCoach(actor, versionId)
        : kernel.readAssignedVersion(actor, actor.tenantId(), assignmentId);
    pa05Step(version, stepId);
    return new MessageScope(actor.tenantId(), assignmentId, versionId, stepId, coach.subjectId(), clientId);
  }

  public synchronized List<StepMessage> stepMessages(Actor actor, MessageScope scope) {
    if (!scope.equals(messageScope(actor, scope.clientId(), scope.assignmentId(), scope.versionId(), scope.stepId())))
      throw new IllegalArgumentException("invalid message scope");
    return messages.values().stream().filter(message -> message.scope().equals(scope)).toList();
  }

  public synchronized StepMessage sendStepMessage(Actor actor, MessageScope scope, String body, String key)
      throws IOException {
    validateMessage(body, key);
    MessageScope current = messageScope(actor, scope.clientId(), scope.assignmentId(), scope.versionId(), scope.stepId());
    if (!scope.equals(current)) throw new IllegalArgumentException("invalid message scope");
    MessageRetry retry = new MessageRetry(actor, key);
    StepMessage prior = messages.get(retry);
    if (prior != null) {
      if (!prior.scope().equals(scope) || !prior.body().equals(body))
        throw new DomainException(ErrorCode.IDEMPOTENCY_CONFLICT, "message intent differs");
      return prior;
    }
    commit(command("step_message", actor, key)
        + ",\"sender_role\":" + JsonMini.quote(actor.role().name())
        + ",\"client_id\":" + JsonMini.quote(scope.clientId())
        + ",\"coach_id\":" + JsonMini.quote(scope.coachId())
        + ",\"assignment_id\":" + JsonMini.quote(scope.assignmentId().toString())
        + ",\"version_id\":" + JsonMini.quote(scope.versionId().toString())
        + ",\"step_id\":" + JsonMini.quote(scope.stepId())
        + ",\"message_id\":" + JsonMini.quote(UUID.randomUUID().toString())
        + ",\"body\":" + JsonMini.quote(body) + "}");
    return messages.get(retry);
  }

  private static void validateMessage(String body, String key) {
    if (body.isBlank() || body.length() > 500 || key.isBlank() || key.length() > 128)
      throw new IllegalArgumentException("invalid step message or retry key");
  }

  public synchronized ProgressState clientProgress(Actor actor, MessageScope scope) {
    requireProgressRole(actor, scope, Role.CLIENT);
    return progress.get(scope);
  }

  public synchronized boolean releasedProgress(Actor actor, MessageScope scope) {
    requireProgressRole(actor, scope, Role.COACH);
    ProgressState state = progress.get(scope);
    return state != null && state.releaseId() != null;
  }

  public synchronized ProgressEvent changeProgress(Actor actor, MessageScope scope, ProgressAction action,
                                                   String key, boolean canonicalPayload) throws IOException {
    requireProgressRole(actor, scope, Role.CLIENT);
    if (key.isBlank() || key.length() > 128) throw new IllegalArgumentException("invalid retry key");
    ProgressRetry retry = new ProgressRetry(actor, key);
    ProgressEvent previous = progressRetries.get(retry);
    if (previous != null && (!previous.scope().equals(scope) || previous.action() != action || !canonicalPayload))
      throw new DomainException(ErrorCode.IDEMPOTENCY_CONFLICT, "progress intent differs");
    if (!canonicalPayload) throw new IllegalArgumentException("progress operation takes an empty object");
    if (previous != null) return previous;

    ProgressState state = progress.get(scope);
    if ((action == ProgressAction.COMPLETE && state != null)
        || (action == ProgressAction.SHARE && state != null && state.releaseId() != null))
      throw new DomainException(ErrorCode.IDEMPOTENCY_CONFLICT, "progress already committed");
    requireTransition(state, action);

    UUID id = UUID.randomUUID();
    commit(JsonMini.write(Map.ofEntries(
        Map.entry("op", "step_progress"), Map.entry("action", action.name()),
        Map.entry("tenant_id", scope.tenantId()), Map.entry("subject_id", actor.subjectId()),
        Map.entry("client_id", scope.clientId()), Map.entry("coach_id", scope.coachId()),
        Map.entry("assignment_id", scope.assignmentId().toString()),
        Map.entry("version_id", scope.versionId().toString()), Map.entry("step_id", scope.stepId()),
        Map.entry("source_ref", PA05_STEP_SOURCE), Map.entry("event_id", id.toString()), Map.entry("key", key))));
    return progressRetries.get(retry);
  }

  private void requireProgressRole(Actor actor, MessageScope scope, Role role) {
    if (actor.role() != role || !scope.equals(messageScope(actor, scope.clientId(), scope.assignmentId(),
        scope.versionId(), scope.stepId())))
      throw new DomainException(ErrorCode.FORBIDDEN, "progress participant required");
  }

  private static void requireTransition(ProgressState state, ProgressAction action) {
    boolean valid = switch (action) {
      case COMPLETE -> state == null;
      case SHARE -> state != null && state.releaseId() == null;
      case REVOKE -> state != null && state.releaseId() != null;
    };
    if (!valid) throw new DomainException(ErrorCode.INVALID, "progress transition unavailable");
  }

  public synchronized MediaLink activeMediaLink(Actor actor, MessageScope scope) {
    requireMediaRole(actor, scope, null);
    UUID id = activeMedia.get(scope);
    if (id == null) throw new DomainException(ErrorCode.NOT_FOUND, "active media link unavailable");
    return mediaLinks.get(id);
  }

  public synchronized MediaLink attachMediaLink(Actor actor, MessageScope scope, String url, String title,
                                                String key) throws IOException {
    requireMediaRole(actor, scope, Role.COACH);
    String canonicalUrl = requireMediaUrl(url);
    requireMediaTitle(title);
    if (key.isBlank() || key.length() > 128) throw new IllegalArgumentException("invalid retry key");
    MediaRetry retry = new MediaRetry(actor, key);
    MediaLinkEvent previous = mediaRetries.get(retry);
    if (previous != null) {
      MediaLink link = previous.link();
      if (!"ATTACH".equals(previous.action()) || !link.scope().equals(scope)
          || !link.url().equals(canonicalUrl) || !link.title().equals(title)
          || !link.ownerId().equals(actor.subjectId()) || link.withdrawn())
        throw new DomainException(ErrorCode.IDEMPOTENCY_CONFLICT, "media intent differs");
      return link;
    }
    if (activeMedia.containsKey(scope))
      throw new DomainException(ErrorCode.IDEMPOTENCY_CONFLICT, "active media link already attached");
    UUID id = UUID.randomUUID();
    commit(JsonMini.write(mediaRecord("coach_media_link_attach", actor, scope, key, id, 1L, id,
        canonicalUrl, title)));
    return mediaLinks.get(id);
  }

  public synchronized MediaLink withdrawMediaLink(Actor actor, MessageScope scope, String key)
      throws IOException {
    requireMediaRole(actor, scope, Role.COACH);
    if (key.isBlank() || key.length() > 128) throw new IllegalArgumentException("invalid retry key");
    MediaRetry retry = new MediaRetry(actor, key);
    MediaLinkEvent previous = mediaRetries.get(retry);
    if (previous != null) {
      if (!"WITHDRAW".equals(previous.action()) || !previous.link().scope().equals(scope)
          || !previous.link().ownerId().equals(actor.subjectId()))
        throw new DomainException(ErrorCode.IDEMPOTENCY_CONFLICT, "media intent differs");
      return previous.link();
    }
    UUID active = activeMedia.get(scope);
    if (active == null) throw new DomainException(ErrorCode.NOT_FOUND, "active media link unavailable");
    MediaLink current = mediaLinks.get(active);
    UUID eventId = UUID.randomUUID();
    commit(JsonMini.write(mediaRecord("coach_media_link_withdraw", actor, scope, key, current.mediaLinkId(),
        current.linkVersion(), eventId, current.url(), current.title())));
    return mediaRetries.get(retry).link();
  }

  private void requireMediaRole(Actor actor, MessageScope scope, Role required) {
    if (required != null && actor.role() != required)
      throw new DomainException(ErrorCode.FORBIDDEN, "coach media access required");
    if (!scope.equals(messageScope(actor, scope.clientId(), scope.assignmentId(), scope.versionId(),
        scope.stepId())) || (actor.role() == Role.COACH && !actor.subjectId().equals(scope.coachId())))
      throw new DomainException(ErrorCode.FORBIDDEN, "assignment participant required");
  }

  private static Map<String, Object> mediaRecord(String op, Actor actor, MessageScope scope, String key,
                                                 UUID mediaLinkId, long version, UUID eventId,
                                                 String url, String title) {
    Map<String, Object> record = new LinkedHashMap<>();
    record.put("op", op);
    record.put("tenant_id", scope.tenantId());
    record.put("subject_id", actor.subjectId());
    record.put("client_id", scope.clientId());
    record.put("coach_id", scope.coachId());
    record.put("assignment_id", scope.assignmentId().toString());
    record.put("version_id", scope.versionId().toString());
    record.put("step_id", scope.stepId());
    record.put("source_ref", PA05_STEP_SOURCE);
    record.put("media_link_id", mediaLinkId.toString());
    record.put("link_version", version);
    record.put("event_id", eventId.toString());
    record.put("url", url);
    record.put("title", title);
    record.put("rights_state", MEDIA_RIGHTS);
    record.put("use", MEDIA_USE);
    record.put("key", key);
    return record;
  }

  static String requireMediaUrl(String raw) {
    if (raw == null || raw.length() < 12 || raw.length() > 2048)
      throw new IllegalArgumentException("invalid media url");
    for (int i = 0; i < raw.length(); i++) {
      char c = raw.charAt(i);
      if (c <= 0x20 || c == '\\' || c == '<' || c == '>' || c == '"' || c == '\'')
        throw new IllegalArgumentException("invalid media url");
    }
    if (raw.indexOf('@') >= 0) throw new IllegalArgumentException("invalid media url");
    URI uri;
    try {
      uri = new URI(raw);
    } catch (URISyntaxException ex) {
      throw new IllegalArgumentException("invalid media url");
    }
    if (!uri.isAbsolute() || uri.isOpaque() || !"https".equals(uri.getScheme())
        || uri.getRawUserInfo() != null || uri.getUserInfo() != null || uri.getHost() == null
        || uri.getPort() != -1)
      throw new IllegalArgumentException("invalid media url");
    String host = uri.getHost();
    if (!host.equals(host.toLowerCase(Locale.ROOT)) || !MEDIA_HOSTS.contains(host)
        || host.chars().allMatch(ch -> ch == '.' || Character.isDigit(ch)))
      throw new IllegalArgumentException("invalid media url");
    String prefix = "https://" + host;
    if (!raw.startsWith(prefix)) throw new IllegalArgumentException("invalid media url");
    if (raw.length() > prefix.length()) {
      char next = raw.charAt(prefix.length());
      if (next != '/' && next != '?' && next != '#') throw new IllegalArgumentException("invalid media url");
    }
    return raw;
  }

  private static void requireMediaTitle(String title) {
    if (title == null || title.isBlank() || title.length() > 120)
      throw new IllegalArgumentException("invalid media title");
    for (int i = 0; i < title.length(); i++) {
      if (title.charAt(i) < 0x20) throw new IllegalArgumentException("invalid media title");
    }
  }

  private void replayMedia(Map<String, Object> record, Actor recordedActor, boolean withdraw) {
    Actor coach = new Actor(recordedActor.tenantId(), recordedActor.subjectId(), Role.COACH);
    MessageScope scope = messageScope(coach, JsonMini.text(record.get("client_id")),
        UUID.fromString(JsonMini.text(record.get("assignment_id"))),
        UUID.fromString(JsonMini.text(record.get("version_id"))), JsonMini.text(record.get("step_id")));
    if (!scope.coachId().equals(record.get("coach_id")) || !PA05_STEP_SOURCE.equals(record.get("source_ref"))
        || !MEDIA_RIGHTS.equals(record.get("rights_state")) || !MEDIA_USE.equals(record.get("use"))
        || !coach.subjectId().equals(scope.coachId()))
      throw new IllegalArgumentException("invalid committed media binding");
    String url = requireMediaUrl(JsonMini.text(record.get("url")));
    String title = JsonMini.text(record.get("title"));
    requireMediaTitle(title);
    UUID mediaLinkId = UUID.fromString(JsonMini.text(record.get("media_link_id")));
    long version = JsonMini.integer(record.get("link_version"));
    UUID eventId = UUID.fromString(JsonMini.text(record.get("event_id")));
    String key = JsonMini.text(record.get("key"));
    if (key.isBlank() || key.length() > 128 || version != 1L
        || mediaRetries.containsKey(new MediaRetry(coach, key))
        || mediaRetries.values().stream().anyMatch(event -> event.eventId().equals(eventId)))
      throw new IllegalArgumentException("duplicate or invalid media event");
    if (withdraw) {
      MediaLink current = mediaLinks.get(mediaLinkId);
      if (current == null || current.withdrawn() || !current.scope().equals(scope)
          || !current.url().equals(url) || !current.title().equals(title)
          || current.linkVersion() != version || !mediaLinkId.equals(activeMedia.get(scope)))
        throw new IllegalArgumentException("invalid committed media withdraw");
      MediaLink withdrawn = new MediaLink(mediaLinkId, version, scope, coach.subjectId(), url, title, true);
      mediaRetries.put(new MediaRetry(coach, key), new MediaLinkEvent(eventId, "WITHDRAW", withdrawn));
      mediaLinks.put(mediaLinkId, withdrawn);
      activeMedia.remove(scope);
      return;
    }
    if (activeMedia.containsKey(scope) || mediaLinks.containsKey(mediaLinkId) || !eventId.equals(mediaLinkId))
      throw new IllegalArgumentException("invalid committed media attach");
    MediaLink link = new MediaLink(mediaLinkId, version, scope, coach.subjectId(), url, title, false);
    mediaRetries.put(new MediaRetry(coach, key), new MediaLinkEvent(eventId, "ATTACH", link));
    mediaLinks.put(mediaLinkId, link);
    activeMedia.put(scope, mediaLinkId);
  }

  private void replayProgress(Map<String, Object> record, Actor recordedActor) {
    Actor client = new Actor(recordedActor.tenantId(), recordedActor.subjectId(), Role.CLIENT);
    MessageScope scope = messageScope(client, JsonMini.text(record.get("client_id")),
        UUID.fromString(JsonMini.text(record.get("assignment_id"))),
        UUID.fromString(JsonMini.text(record.get("version_id"))), JsonMini.text(record.get("step_id")));
    if (!scope.coachId().equals(record.get("coach_id")) || !PA05_STEP_SOURCE.equals(record.get("source_ref")))
      throw new IllegalArgumentException("invalid committed progress binding");
    ProgressAction action = ProgressAction.valueOf(JsonMini.text(record.get("action")));
    ProgressState state = progress.get(scope);
    requireTransition(state, action);
    UUID id = UUID.fromString(JsonMini.text(record.get("event_id")));
    String key = JsonMini.text(record.get("key"));
    if (key.isBlank() || key.length() > 128 || progressRetries.containsKey(new ProgressRetry(client, key))
        || progressRetries.values().stream().anyMatch(event -> event.id().equals(id)))
      throw new IllegalArgumentException("duplicate or invalid progress event");
    progressRetries.put(new ProgressRetry(client, key), new ProgressEvent(id, scope, action));
    progress.put(scope, switch (action) {
      case COMPLETE -> new ProgressState(id, null);
      case SHARE -> new ProgressState(state.completionId(), id);
      case REVOKE -> new ProgressState(state.completionId(), null);
    });
  }

  private static Object stepSource(JourneyJournal.Projection projection, String stepId) {
    Object parsed = JsonMini.parse(projection.phasesJson());
    if (!(parsed instanceof List<?> phases)) return null;
    Map<?, ?> matchedStep = null;
    for (Object phase : phases) {
      if (!(phase instanceof Map<?, ?> fields) || !(fields.get("steps") instanceof List<?> steps)) return null;
      for (Object step : steps) {
        if (!(step instanceof Map<?, ?> fieldsOfStep)) return null;
        if (stepId.equals(fieldsOfStep.get("step_id"))) {
          if (matchedStep != null) return null;
          matchedStep = fieldsOfStep;
        }
      }
    }
    return matchedStep == null ? null : matchedStep.get("source_ref");
  }

  private void apply(String line) {
    Map<String, Object> command = JsonMini.object(JsonMini.parse(line));
    Actor actor = new Actor(JsonMini.text(command.get("tenant_id")),
                             JsonMini.text(command.get("subject_id")), Role.COACH);
    switch (JsonMini.text(command.get("op"))) {
      case "create" -> {
        UUID draftId = UUID.fromString(JsonMini.text(command.get("draft_id")));
        kernel.createDraft(actor, actor.tenantId(),
            JsonMini.text(command.get("title")), JsonMini.text(command.get("key")), draftId);
        rememberOrigin(draftId, command.get("origin"));
      }
      case "update" -> {
        UUID draftId = UUID.fromString(JsonMini.text(command.get("draft_id")));
        List<Step> steps = readSteps(command.get("steps"));
        kernel.updateDraft(actor, actor.tenantId(), draftId,
            JsonMini.integer(command.get("expected_revision")),
            JsonMini.text(command.get("title")), steps);
        if (command.get("phases_json") instanceof String phases) draftPhases.put(draftId, phases);
        rememberOrigin(draftId, command.get("origin"));
        rememberC19History(draftId, steps);
      }
      case "c19_local_review" -> replayLocalReview(command, actor);
      case "publish" -> {
        UUID draftId = UUID.fromString(JsonMini.text(command.get("draft_id")));
        var view = kernel.publish(actor, actor.tenantId(), draftId,
            JsonMini.integer(command.get("expected_revision")),
            JsonMini.text(command.get("key")));
        if (command.get("phases_json") instanceof String phases) {
          String state = projections.containsKey(view.journeyVersionId())
              ? projections.get(view.journeyVersionId()).publicationState() : "PUBLISHED";
          projections.put(view.journeyVersionId(), new Projection(actor.tenantId(), draftId.toString(),
              view.journeyVersionId().toString(), phases, JsonMini.text(command.get("content_hash")),
              JsonMini.text(command.get("published_at")), state));
        }
      }
      case "assign" -> {
        var view = kernel.assign(actor, actor.tenantId(),
            JsonMini.text(command.get("client_id")),
            UUID.fromString(JsonMini.text(command.get("version_id"))),
            Boolean.TRUE.equals(command.get("consent_verified")),
            JsonMini.text(command.get("key")),
            UUID.fromString(JsonMini.text(command.get("assignment_id"))));
        assigningCoaches.putIfAbsent(view.assignmentId(), actor);
        String enrollmentId = JsonMini.text(command.get("enrollment_id"));
        enrollments.put(UUID.fromString(enrollmentId), new EnrollmentLink(actor.tenantId(),
            view.clientId(), view.journeyVersionId().toString(), view.assignmentId().toString(), enrollmentId));
      }
      case "step_message" -> {
        Actor sender = new Actor(actor.tenantId(), actor.subjectId(),
            Role.valueOf(JsonMini.text(command.get("sender_role"))));
        MessageScope scope = messageScope(sender, JsonMini.text(command.get("client_id")),
            UUID.fromString(JsonMini.text(command.get("assignment_id"))),
            UUID.fromString(JsonMini.text(command.get("version_id"))), JsonMini.text(command.get("step_id")));
        String body = JsonMini.text(command.get("body"));
        String key = JsonMini.text(command.get("key"));
        validateMessage(body, key);
        UUID id = UUID.fromString(JsonMini.text(command.get("message_id")));
        if (!scope.coachId().equals(command.get("coach_id"))
            || messages.values().stream().anyMatch(message -> message.id().equals(id))
            || messages.putIfAbsent(new MessageRetry(sender, key), new StepMessage(id, scope, sender, body)) != null)
          throw new IllegalArgumentException("invalid or duplicate step message");
      }
      case "step_progress" -> replayProgress(command, actor);
      case "coach_media_link_attach" -> replayMedia(command, actor, false);
      case "coach_media_link_withdraw" -> replayMedia(command, actor, true);
      case "withdraw" -> {
        UUID versionId = UUID.fromString(JsonMini.text(command.get("version_id")));
        kernel.withdraw(actor, actor.tenantId(), versionId);
        Projection prior = projections.get(versionId);
        if (prior != null) projections.put(versionId, new Projection(prior.tenantId(), prior.journeyId(),
            prior.versionId(), prior.phasesJson(), prior.contentHash(), prior.publishedAt(), "WITHDRAWN"));
      }
      default -> throw new IllegalArgumentException("unknown journal command");
    }
  }

  @SuppressWarnings("unchecked")
  private static List<Step> readSteps(Object value) {
    if (!(value instanceof List<?> list)) throw new IllegalArgumentException("steps required");
    List<Step> steps = new ArrayList<>();
    for (Object item : list) {
      Map<String, Object> step = (Map<String, Object>) item;
      steps.add(new Step(JsonMini.text(step.get("step_id")), JsonMini.text(step.get("title")),
          new CanonicalPin(JsonMini.text(step.get("published_version_ref")),
                           JsonMini.text(step.get("receipt_sha256")),
                           Boolean.TRUE.equals(step.get("approved")),
                           Boolean.TRUE.equals(step.get("rights_granted")))));
    }
    return List.copyOf(steps);
  }

  private static String stepsJson(List<Step> steps) {
    StringBuilder out = new StringBuilder("[");
    for (int i = 0; i < steps.size(); i++) {
      if (i > 0) out.append(',');
      Step step = steps.get(i);
      out.append("{\"step_id\":").append(JsonMini.quote(step.stepId()))
         .append(",\"title\":").append(JsonMini.quote(step.title()))
         .append(",\"published_version_ref\":").append(JsonMini.quote(step.canonicalPin().publishedVersionRef()))
         .append(",\"receipt_sha256\":").append(JsonMini.quote(step.canonicalPin().receiptSha256()))
         .append(",\"approved\":").append(step.canonicalPin().approved())
         .append(",\"rights_granted\":").append(step.canonicalPin().rightsGranted())
         .append('}');
    }
    return out.append(']').toString();
  }

  private boolean c19PublishDenied(Actor actor, UUID draftId) {
    if (C19LocalReview.ORIGIN.equals(draftOrigins.get(draftId))) return true;
    if (c19PinHistory.contains(draftId)) return true;
    DraftView draft = kernel.readDraft(actor, draftId);
    if (draft.steps().isEmpty()) return false;
    GoalProposalAdapter adapter = new GoalProposalAdapter();
    for (Step step : draft.steps()) {
      if (adapter.isAdmittedC19Pin(step.canonicalPin())) return true;
    }
    return false;
  }

  private void rememberC19History(UUID draftId, List<Step> steps) {
    if (c19PinHistory.contains(draftId) || steps == null) return;
    GoalProposalAdapter adapter = new GoalProposalAdapter();
    for (Step step : steps) {
      if (adapter.isAdmittedC19Pin(step.canonicalPin())) {
        c19PinHistory.add(draftId);
        return;
      }
    }
  }

  private DraftView requireC19Draft(Actor actor, UUID draftId, long expectedRevision) {
    DraftView draft = kernel.readDraft(actor, draftId);
    if (!C19LocalReview.ORIGIN.equals(draftOrigins.get(draftId)))
      throw new DomainException(ErrorCode.INVALID, "C19 draft origin required");
    if (!"draft".equals(draft.status()))
      throw new DomainException(ErrorCode.INVALID, "C19 draft is not reviewable");
    if (draft.revision() != expectedRevision)
      throw new DomainException(ErrorCode.STALE_REVISION, "expected draft revision differs");
    GoalProposalAdapter adapter = new GoalProposalAdapter();
    for (Step step : draft.steps()) adapter.requireCurrentPin(step.canonicalPin());
    return draft;
  }

  private void replayLocalReview(Map<String, Object> command, Actor actor) {
    UUID draftId = UUID.fromString(JsonMini.text(command.get("draft_id")));
    long expectedRevision = JsonMini.integer(command.get("expected_revision"));
    String key = JsonMini.text(command.get("key"));
    String storedDigest = JsonMini.text(command.get("digest"));
    DraftView draft = requireC19Draft(actor, draftId, expectedRevision);
    String digest = C19LocalReview.digest(draft);
    if (!digest.equals(storedDigest))
      throw new IllegalArgumentException("local review digest does not match persisted draft");
    C19LocalReview.Receipt receipt = new C19LocalReview.Receipt(
        draftId, expectedRevision, digest, actor.tenantId(), actor.subjectId(), key, true);
    ReviewRetry retry = new ReviewRetry(actor.tenantId(), actor.subjectId(), key);
    C19LocalReview.Receipt existing = reviewRetries.putIfAbsent(retry, receipt);
    if (existing != null && (!existing.draftId().equals(draftId) || existing.revision() != expectedRevision
        || !existing.digest().equals(digest)))
      throw new IllegalArgumentException("invalid or duplicate local review");
    reviews.put(draftId, receipt);
  }

  private void rememberOrigin(UUID draftId, Object originValue) {
    if (!(originValue instanceof String origin) || origin.isBlank()) return;
    if (!C19LocalReview.ORIGIN.equals(origin))
      throw new IllegalArgumentException("unknown draft origin");
    draftOrigins.put(draftId, origin);
  }

  private static String originField(String origin) {
    if (origin == null || origin.isBlank()) return "";
    if (!C19LocalReview.ORIGIN.equals(origin))
      throw new IllegalArgumentException("unknown draft origin");
    return ",\"origin\":" + JsonMini.quote(origin);
  }

  private static String command(String op, Actor actor, String key) {
    StringBuilder out = new StringBuilder("{\"op\":").append(JsonMini.quote(op))
        .append(",\"tenant_id\":").append(JsonMini.quote(actor.tenantId()))
        .append(",\"subject_id\":").append(JsonMini.quote(actor.subjectId()));
    if (key != null) out.append(",\"key\":").append(JsonMini.quote(key));
    return out.toString();
  }

  private static String sha256(String value) {
    try {
      byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
      return HexFormat.of().formatHex(digest);
    } catch (Exception ex) {
      throw new IllegalStateException("SHA-256 is unavailable");
    }
  }

  private void commit(String line) throws IOException {
    if (line.indexOf('\n') >= 0 || line.indexOf('\r') >= 0)
      throw new IOException("journal record must be one line");
    sink.commit(path, line);
    apply(line);
  }

  private static void discardUncommittedTail(Path path) throws IOException {
    if (!Files.exists(path) || Files.isDirectory(path)) return;
    byte[] bytes = Files.readAllBytes(path);
    if (bytes.length == 0 || bytes[bytes.length - 1] == '\n') return;
    int end = bytes.length - 1;
    while (end >= 0 && bytes[end] != '\n') end--;
    try (FileChannel channel = FileChannel.open(path, StandardOpenOption.WRITE)) {
      channel.truncate(end + 1L);
      channel.force(true);
    }
  }

  static final class DurableCommit implements JournalCommit {
    static final DurableCommit INSTANCE = new DurableCommit();

    public void commit(Path path, String line) throws IOException {
      byte[] payload = (line + "\n").getBytes(StandardCharsets.UTF_8);
      long committed = Files.exists(path) && !Files.isDirectory(path) ? Files.size(path) : 0L;
      try (FileChannel channel = FileChannel.open(path, StandardOpenOption.CREATE, StandardOpenOption.WRITE,
          StandardOpenOption.DSYNC)) {
        try {
          channel.position(committed);
          ByteBuffer buffer = ByteBuffer.wrap(payload);
          while (buffer.hasRemaining()) {
            int wrote = channel.write(buffer);
            if (wrote <= 0) throw new IOException("journal short write");
          }
          channel.force(true);
          if (channel.size() != committed + payload.length) throw new IOException("journal partial commit");
        } catch (IOException ex) {
          channel.truncate(committed);
          channel.force(true);
          throw ex;
        }
      }
    }
  }
}
