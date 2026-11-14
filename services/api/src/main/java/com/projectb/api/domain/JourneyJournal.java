package com.projectb.api.domain;

import java.io.IOException;
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
import java.util.Map;
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

  private final Path path;
  private final JournalCommit sink;
  private final JourneyKernel kernel = new JourneyKernel();
  private final Map<UUID, String> draftPhases = new LinkedHashMap<>();
  private final Map<UUID, Projection> projections = new LinkedHashMap<>();
  private final Map<UUID, EnrollmentLink> enrollments = new LinkedHashMap<>();

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
    DraftView existing = kernel.peekCreate(actor, actor.tenantId(), title, key);
    if (existing != null) return existing;
    UUID draftId = UUID.randomUUID();
    commit(command("create", actor, key)
        + ",\"title\":" + JsonMini.quote(title)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString()) + "}");
    DraftView created = kernel.peekCreate(actor, actor.tenantId(), title, key);
    if (created == null) throw new IOException("committed create was not visible");
    return created;
  }

  public synchronized DraftView updateDraft(Actor actor, UUID draftId, long expectedRevision,
                                            String title, List<Step> steps, String phasesJson) throws IOException {
    kernel.validateUpdateDraft(actor, actor.tenantId(), draftId, expectedRevision, title, steps);
    commit(command("update", actor, null)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + ",\"expected_revision\":" + expectedRevision
        + ",\"title\":" + JsonMini.quote(title)
        + ",\"steps\":" + stepsJson(steps)
        + (phasesJson == null ? "" : ",\"phases_json\":" + JsonMini.quote(phasesJson)) + "}");
    return kernel.readDraft(actor, draftId);
  }

  public synchronized PublishedView publish(Actor actor, UUID draftId, long expectedRevision,
                                            String key) throws IOException {
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
      case "create" -> kernel.createDraft(actor, actor.tenantId(),
          JsonMini.text(command.get("title")), JsonMini.text(command.get("key")),
          UUID.fromString(JsonMini.text(command.get("draft_id"))));
      case "update" -> {
        UUID draftId = UUID.fromString(JsonMini.text(command.get("draft_id")));
        kernel.updateDraft(actor, actor.tenantId(), draftId,
            JsonMini.integer(command.get("expected_revision")),
            JsonMini.text(command.get("title")), readSteps(command.get("steps")));
        if (command.get("phases_json") instanceof String phases) draftPhases.put(draftId, phases);
      }
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
