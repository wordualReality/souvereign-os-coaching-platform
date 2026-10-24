package com.projectb.api.domain;

import java.io.IOException;
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
import com.projectb.api.domain.JourneyKernel.PublishedView;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.domain.JourneyKernel.Step;
import com.projectb.api.json.JsonMini;

/**
 * Append-only command journal for one local journey service.
 * Recovery rebuilds the kernel by applying each successful command once.
 * A client request body is never copied in as a consent authority.
 */
public final class JourneyJournal {
  public record Projection(String tenantId, String journeyId, String versionId, String phasesJson,
                          String contentHash, String publishedAt, String publicationState) {}
  public record EnrollmentLink(String tenantId, String clientId, String versionId,
                               String assignmentId, String enrollmentId) {}

  private final Path path;
  private final JourneyKernel kernel = new JourneyKernel();
  private final Map<UUID, String> draftPhases = new LinkedHashMap<>();
  private final Map<UUID, Projection> projections = new LinkedHashMap<>();
  private final Map<UUID, EnrollmentLink> enrollments = new LinkedHashMap<>();

  private JourneyJournal(Path path) { this.path = path; }

  public static JourneyJournal open(Path path) throws IOException {
    JourneyJournal journal = new JourneyJournal(path);
    if (Files.exists(path)) {
      for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
        if (!line.isBlank()) journal.apply(line);
      }
    }
    return journal;
  }

  public JourneyKernel kernel() { return kernel; }

  public synchronized DraftView createDraft(Actor actor, String title, String key) throws IOException {
    DraftView view = kernel.createDraft(actor, actor.tenantId(), title, key);
    append(command("create", actor, key)
        + ",\"title\":" + JsonMini.quote(title)
        + ",\"draft_id\":" + JsonMini.quote(view.draftId().toString()) + "}");
    return view;
  }

  public synchronized DraftView updateDraft(Actor actor, UUID draftId, long expectedRevision,
                                            String title, List<Step> steps, String phasesJson) throws IOException {
    DraftView view = kernel.updateDraft(actor, actor.tenantId(), draftId, expectedRevision, title, steps);
    if (phasesJson != null) draftPhases.put(draftId, phasesJson);
    append(command("update", actor, null)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + ",\"expected_revision\":" + expectedRevision
        + ",\"title\":" + JsonMini.quote(title)
        + ",\"steps\":" + stepsJson(steps)
        + (phasesJson == null ? "" : ",\"phases_json\":" + JsonMini.quote(phasesJson)) + "}");
    return view;
  }

  public synchronized PublishedView publish(Actor actor, UUID draftId, long expectedRevision,
                                            String key) throws IOException {
    PublishedView view = kernel.publish(actor, actor.tenantId(), draftId, expectedRevision, key);
    String phases = draftPhases.getOrDefault(draftId, "[]");
    Projection prior = projections.get(view.journeyVersionId());
    String publishedAt = prior == null ? Instant.now().toString() : prior.publishedAt();
    String hash = sha256(phases);
    projections.put(view.journeyVersionId(), new Projection(actor.tenantId(), view.sourceDraftId().toString(),
        view.journeyVersionId().toString(), phases, hash, publishedAt,
        prior == null ? "PUBLISHED" : prior.publicationState()));
    append(command("publish", actor, key)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + ",\"expected_revision\":" + expectedRevision
        + ",\"version_id\":" + JsonMini.quote(view.journeyVersionId().toString())
        + ",\"phases_json\":" + JsonMini.quote(phases)
        + ",\"content_hash\":" + JsonMini.quote(hash)
        + ",\"published_at\":" + JsonMini.quote(publishedAt) + "}");
    return view;
  }

  public synchronized AssignmentView assign(Actor actor, String clientId, UUID versionId,
                                            boolean consentVerified, String key) throws IOException {
    AssignmentView view = kernel.assign(actor, actor.tenantId(), clientId, versionId, consentVerified, key);
    String enrollmentId = UUID.nameUUIDFromBytes(("enrollment/" + view.assignmentId())
        .getBytes(StandardCharsets.UTF_8)).toString();
    enrollments.put(UUID.fromString(enrollmentId), new EnrollmentLink(actor.tenantId(), clientId,
        versionId.toString(), view.assignmentId().toString(), enrollmentId));
    append(command("assign", actor, key)
        + ",\"client_id\":" + JsonMini.quote(clientId)
        + ",\"version_id\":" + JsonMini.quote(versionId.toString())
        + ",\"assignment_id\":" + JsonMini.quote(view.assignmentId().toString())
        + ",\"enrollment_id\":" + JsonMini.quote(enrollmentId)
        + ",\"consent_verified\":" + consentVerified + "}");
    return view;
  }

  public synchronized PublishedView withdraw(Actor actor, UUID versionId) throws IOException {
    PublishedView view = kernel.withdraw(actor, actor.tenantId(), versionId);
    Projection prior = projections.get(versionId);
    if (prior != null) {
      projections.put(versionId, new Projection(prior.tenantId(), prior.journeyId(), prior.versionId(),
          prior.phasesJson(), prior.contentHash(), prior.publishedAt(), "WITHDRAWN"));
    }
    append(command("withdraw", actor, null)
        + ",\"version_id\":" + JsonMini.quote(versionId.toString()) + "}");
    return view;
  }

  public synchronized Projection projection(UUID versionId) { return projections.get(versionId); }

  public synchronized EnrollmentLink enrollment(UUID enrollmentId) { return enrollments.get(enrollmentId); }

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
        String enrollmentId = JsonMini.text(command.get("enrollment_id"));
        enrollments.put(UUID.fromString(enrollmentId), new EnrollmentLink(actor.tenantId(),
            view.clientId(), view.journeyVersionId().toString(), view.assignmentId().toString(), enrollmentId));
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

  private void append(String line) throws IOException {
    Files.writeString(path, line + "\n", StandardCharsets.UTF_8,
        StandardOpenOption.CREATE, StandardOpenOption.APPEND, StandardOpenOption.DSYNC);
  }
}
