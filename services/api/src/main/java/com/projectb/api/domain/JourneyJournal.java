package com.projectb.api.domain;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
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
  private final Path path;
  private final JourneyKernel kernel = new JourneyKernel();

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
                                            String title, List<Step> steps) throws IOException {
    DraftView view = kernel.updateDraft(actor, actor.tenantId(), draftId, expectedRevision, title, steps);
    append(command("update", actor, null)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + ",\"expected_revision\":" + expectedRevision
        + ",\"title\":" + JsonMini.quote(title)
        + ",\"steps\":" + stepsJson(steps) + "}");
    return view;
  }

  public synchronized PublishedView publish(Actor actor, UUID draftId, long expectedRevision,
                                            String key) throws IOException {
    PublishedView view = kernel.publish(actor, actor.tenantId(), draftId, expectedRevision, key);
    append(command("publish", actor, key)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + ",\"expected_revision\":" + expectedRevision + "}");
    return view;
  }

  public synchronized AssignmentView assign(Actor actor, String clientId, UUID versionId,
                                            boolean consentVerified, String key) throws IOException {
    AssignmentView view = kernel.assign(actor, actor.tenantId(), clientId, versionId, consentVerified, key);
    append(command("assign", actor, key)
        + ",\"client_id\":" + JsonMini.quote(clientId)
        + ",\"version_id\":" + JsonMini.quote(versionId.toString())
        + ",\"assignment_id\":" + JsonMini.quote(view.assignmentId().toString())
        + ",\"consent_verified\":" + consentVerified + "}");
    return view;
  }

  public synchronized PublishedView withdraw(Actor actor, UUID versionId) throws IOException {
    PublishedView view = kernel.withdraw(actor, actor.tenantId(), versionId);
    append(command("withdraw", actor, null)
        + ",\"version_id\":" + JsonMini.quote(versionId.toString()) + "}");
    return view;
  }

  private void apply(String line) {
    Map<String, Object> command = JsonMini.object(JsonMini.parse(line));
    Actor actor = new Actor(JsonMini.text(command.get("tenant_id")),
                             JsonMini.text(command.get("subject_id")), Role.COACH);
    switch (JsonMini.text(command.get("op"))) {
      case "create" -> kernel.createDraft(actor, actor.tenantId(),
          JsonMini.text(command.get("title")), JsonMini.text(command.get("key")),
          UUID.fromString(JsonMini.text(command.get("draft_id"))));
      case "update" -> kernel.updateDraft(actor, actor.tenantId(),
          UUID.fromString(JsonMini.text(command.get("draft_id"))),
          JsonMini.integer(command.get("expected_revision")),
          JsonMini.text(command.get("title")), readSteps(command.get("steps")));
      case "publish" -> kernel.publish(actor, actor.tenantId(),
          UUID.fromString(JsonMini.text(command.get("draft_id"))),
          JsonMini.integer(command.get("expected_revision")),
          JsonMini.text(command.get("key")));
      case "assign" -> kernel.assign(actor, actor.tenantId(),
          JsonMini.text(command.get("client_id")),
          UUID.fromString(JsonMini.text(command.get("version_id"))),
          Boolean.TRUE.equals(command.get("consent_verified")),
          JsonMini.text(command.get("key")),
          UUID.fromString(JsonMini.text(command.get("assignment_id"))));
      case "withdraw" -> kernel.withdraw(actor, actor.tenantId(),
          UUID.fromString(JsonMini.text(command.get("version_id"))));
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

  private void append(String line) throws IOException {
    Files.writeString(path, line + "\n", StandardCharsets.UTF_8,
        StandardOpenOption.CREATE, StandardOpenOption.APPEND, StandardOpenOption.DSYNC);
  }
}
