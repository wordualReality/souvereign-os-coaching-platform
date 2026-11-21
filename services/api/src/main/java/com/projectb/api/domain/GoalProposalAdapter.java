package com.projectb.api.domain;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import com.projectb.api.domain.JourneyKernel.CanonicalPin;
import com.projectb.api.domain.JourneyKernel.DomainException;
import com.projectb.api.domain.JourneyKernel.ErrorCode;
import com.projectb.api.domain.JourneyKernel.Step;

/**
 * Deterministic TEST_LOOPBACK_ONLY outline adapter.
 * Two synthetic coaching-course candidates are the only admitted sources.
 * This is not a KDB, PIAC or live-model runtime.
 */
public final class GoalProposalAdapter {
  public static final String PROFILE = "TEST_LOOPBACK_ONLY";
  public static final String PROPOSAL_KIND = "ARCAVA_C19_GOAL_DRAFT_PROPOSAL";
  public static final String PURPOSE_COURSE = "COACHING_COURSE";
  public static final String PURPOSE_PERSONAL_PREVIEW = "PERSONAL_PLAN_PREVIEW";
  public static final String RIGHTS = "SYNTHETIC_TEST_ONLY";
  public static final String LIFECYCLE_ACTIVE = "ACTIVE";
  public static final String LIFECYCLE_WITHDRAWN = "WITHDRAWN";
  public static final String CALM_ID = "c19.synthetic.course.calm-foundation";
  public static final String FOCUS_ID = "c19.synthetic.course.focus-reset";
  public static final String CALM_VERSION = "c19-calm-v1";
  public static final String FOCUS_VERSION = "c19-focus-v1";
  public static final String CALM_HASH = "c19a111111111111111111111111111111111111111111111111111111111111";
  public static final String FOCUS_HASH = "c19b222222222222222222222222222222222222222222222222222222222222";
  public static final String WITHDRAWN_ID = "c19.synthetic.course.withdrawn-module";
  public static final String PERSONAL_ID = "kdb.pd01.morning-checkin";
  public static final String REVOKED_ID = "c19.synthetic.course.revoked-rights";
  public static final String TAXONOMY = "c19-0000-4000-8000-000000000001";

  public static final class AdapterFailure extends RuntimeException {
    private static final long serialVersionUID = 1L;
    public AdapterFailure(String message) { super(message); }
  }

  public record Candidate(String candidateId, String version, String contentHash, String purpose,
                          String rightsState, boolean rightsGranted, String lifecycle, String title) {}

  public record ProposedStep(String stepId, String title, int ordinal, Candidate source) {}

  public record Proposal(String learningGoal, List<Candidate> candidates, List<ProposedStep> steps,
                         String gap) {
    public Proposal {
      candidates = List.copyOf(candidates);
      steps = List.copyOf(steps);
    }
  }

  private static final Map<String, Candidate> CATALOG = catalog();

  private static Map<String, Candidate> catalog() {
    Map<String, Candidate> catalog = new LinkedHashMap<>();
    catalog.put(CALM_ID, new Candidate(CALM_ID, CALM_VERSION, CALM_HASH, PURPOSE_COURSE, RIGHTS, true,
        LIFECYCLE_ACTIVE, "Synthetic calm foundation"));
    catalog.put(FOCUS_ID, new Candidate(FOCUS_ID, FOCUS_VERSION, FOCUS_HASH, PURPOSE_COURSE, RIGHTS, true,
        LIFECYCLE_ACTIVE, "Synthetic focus reset"));
    catalog.put(WITHDRAWN_ID, new Candidate(WITHDRAWN_ID, "c19-withdrawn-v1",
        "c19c333333333333333333333333333333333333333333333333333333333333", PURPOSE_COURSE, RIGHTS, true,
        LIFECYCLE_WITHDRAWN, "Withdrawn synthetic module"));
    catalog.put(PERSONAL_ID, new Candidate(PERSONAL_ID, "pd01-preview-v1",
        "c19d444444444444444444444444444444444444444444444444444444444444", PURPOSE_PERSONAL_PREVIEW, RIGHTS, true,
        LIFECYCLE_ACTIVE, "Personal plan preview fixture"));
    catalog.put(REVOKED_ID, new Candidate(REVOKED_ID, "c19-revoked-v1",
        "c19e555555555555555555555555555555555555555555555555555555555555", PURPOSE_COURSE, RIGHTS, false,
        LIFECYCLE_ACTIVE, "Revoked-rights synthetic module"));
    return Map.copyOf(catalog);
  }

  public Proposal propose(String learningGoal, List<String> candidateIds, boolean forceError) {
    if (forceError) throw new AdapterFailure("synthetic proposal adapter unavailable");
    requireGoal(learningGoal);
    if (candidateIds == null || candidateIds.isEmpty())
      throw new DomainException(ErrorCode.INVALID, "candidate ids required");
    List<Candidate> selected = new ArrayList<>();
    for (String id : candidateIds) selected.add(requireUsable(id, null, null));
    if (selected.size() != 2 || !CALM_ID.equals(selected.get(0).candidateId())
        || !FOCUS_ID.equals(selected.get(1).candidateId()))
      throw new DomainException(ErrorCode.INVALID, "exactly the two synthetic course candidates are required");
    Candidate calm = selected.get(0);
    Candidate focus = selected.get(1);
    List<ProposedStep> steps = List.of(
        new ProposedStep("step.c19.settle", "Settle the breath", 1, calm),
        new ProposedStep("step.c19.focus", "Reset attention", 2, focus),
        new ProposedStep("step.c19.close", "Close the practice", 3, calm));
    return new Proposal(learningGoal, selected, steps, null);
  }

  public List<Step> kernelSteps(List<ProposedStep> steps) {
    if (steps == null || steps.isEmpty()) throw new DomainException(ErrorCode.INVALID, "at least one step required");
    List<Step> kernel = new ArrayList<>();
    for (ProposedStep step : steps) {
      Candidate source = requireUsable(step.source().candidateId(), step.source().version(),
          step.source().contentHash());
      kernel.add(new Step(step.stepId(), step.title(),
          new CanonicalPin(source.candidateId() + "@" + source.version(), source.contentHash(), true, true)));
    }
    return List.copyOf(kernel);
  }

  public List<ProposedStep> parseEdited(Object rawSteps) {
    if (!(rawSteps instanceof List<?> list) || list.isEmpty())
      throw new DomainException(ErrorCode.INVALID, "edited steps required");
    List<ProposedStep> steps = new ArrayList<>();
    int ordinal = 1;
    for (Object item : list) {
      if (!(item instanceof Map<?, ?> fields)) throw new DomainException(ErrorCode.INVALID, "step object required");
      String stepId = text(fields.get("step_id"));
      String title = text(fields.get("title"));
      Object sourceValue = fields.get("source");
      if (!(sourceValue instanceof Map<?, ?> sourceFields))
        throw new DomainException(ErrorCode.INVALID, "step source required");
      Candidate claimed = new Candidate(text(sourceFields.get("candidate_id")), text(sourceFields.get("version")),
          text(sourceFields.get("content_hash")), stringOrEmpty(sourceFields.get("purpose")),
          stringOrEmpty(sourceFields.get("rights_state")), Boolean.TRUE.equals(sourceFields.get("rights_granted")),
          stringOrEmpty(sourceFields.get("lifecycle")), "");
      Candidate trusted = requireUsable(claimed.candidateId(), claimed.version(), claimed.contentHash());
      steps.add(new ProposedStep(stepId, title, ordinal++, trusted));
    }
    return List.copyOf(steps);
  }

  public Map<String, Object> json(Proposal proposal) {
    Map<String, Object> data = new LinkedHashMap<>();
    data.put("profile", PROFILE);
    data.put("proposal_kind", PROPOSAL_KIND);
    data.put("publication_state", "UNSAVED_PREVIEW");
    data.put("test_only", true);
    data.put("no_live_kdb", true);
    data.put("learning_goal", proposal.learningGoal());
    data.put("candidates", proposal.candidates().stream().map(GoalProposalAdapter::candidateJson).toList());
    data.put("steps", proposal.steps().stream().map(GoalProposalAdapter::stepJson).toList());
    if (proposal.gap() != null) data.put("gap", proposal.gap());
    return data;
  }

  public Map<String, Object> stepJsonMap(ProposedStep step) {
    return stepJson(step);
  }

  public Map<String, Object> sourcedKernelStep(Step step) {
    Map<String, Object> json = new LinkedHashMap<>();
    json.put("step_id", step.stepId());
    json.put("title", step.title());
    CanonicalPin pin = step.canonicalPin();
    json.put("published_version_ref", pin.publishedVersionRef());
    json.put("receipt_sha256", pin.receiptSha256());
    json.put("approved", pin.approved());
    json.put("rights_granted", pin.rightsGranted());
    String ref = pin.publishedVersionRef();
    int at = ref.lastIndexOf('@');
    if (at > 0) {
      Candidate found = CATALOG.get(ref.substring(0, at));
      if (found != null && found.version().equals(ref.substring(at + 1))
          && found.contentHash().equals(pin.receiptSha256())) {
        json.put("source", sourceRef(found));
      }
    }
    return json;
  }

  public String phasesJson(List<ProposedStep> steps) {
    List<Map<String, Object>> phaseSteps = new ArrayList<>();
    for (ProposedStep step : steps) {
      Map<String, Object> row = new LinkedHashMap<>();
      row.put("step_id", step.stepId());
      row.put("title", step.title());
      row.put("source_ref", sourceRef(step.source()));
      phaseSteps.add(row);
    }
    return com.projectb.api.json.JsonMini.write(List.of(Map.of("title", "C19 outline", "steps", phaseSteps)));
  }

  private Candidate requireUsable(String candidateId, String version, String hash) {
    Candidate found = CATALOG.get(candidateId);
    if (found == null) throw new DomainException(ErrorCode.INVALID, "unknown source candidate");
    if (LIFECYCLE_WITHDRAWN.equals(found.lifecycle()))
      throw new DomainException(ErrorCode.WITHDRAWN, "source candidate withdrawn");
    if (!found.rightsGranted() || !RIGHTS.equals(found.rightsState()))
      throw new DomainException(ErrorCode.UNPUBLISHED_CANONICAL, "source rights are not granted");
    if (!PURPOSE_COURSE.equals(found.purpose()))
      throw new DomainException(ErrorCode.UNPUBLISHED_CANONICAL, "source purpose is not a coaching course");
    if (version != null && !found.version().equals(version))
      throw new DomainException(ErrorCode.INVALID, "source version does not match the pinned candidate");
    if (hash != null && !found.contentHash().equals(hash))
      throw new DomainException(ErrorCode.UNPUBLISHED_CANONICAL, "source integrity does not match the pinned candidate");
    return found;
  }

  private static void requireGoal(String learningGoal) {
    if (learningGoal == null || learningGoal.isBlank() || learningGoal.length() > 200)
      throw new DomainException(ErrorCode.INVALID, "learning goal required");
  }

  private static String text(Object value) {
    if (!(value instanceof String text) || text.isBlank())
      throw new DomainException(ErrorCode.INVALID, "source field required");
    return text;
  }

  private static String stringOrEmpty(Object value) {
    return value instanceof String text ? text : "";
  }

  private static Map<String, Object> candidateJson(Candidate candidate) {
    Map<String, Object> json = new LinkedHashMap<>();
    json.put("candidate_id", candidate.candidateId());
    json.put("version", candidate.version());
    json.put("content_hash", candidate.contentHash());
    json.put("purpose", candidate.purpose());
    json.put("rights_state", candidate.rightsState());
    json.put("rights_granted", candidate.rightsGranted());
    json.put("lifecycle", candidate.lifecycle());
    json.put("title", candidate.title());
    json.put("taxonomy_version_id", TAXONOMY);
    json.put("test_only", true);
    return json;
  }

  private static Map<String, Object> stepJson(ProposedStep step) {
    Map<String, Object> json = new LinkedHashMap<>();
    json.put("step_id", step.stepId());
    json.put("title", step.title());
    json.put("ordinal", (long) step.ordinal());
    json.put("source", sourceRef(step.source()));
    return json;
  }

  private static Map<String, Object> sourceRef(Candidate candidate) {
    Map<String, Object> json = candidateJson(candidate);
    json.remove("title");
    return json;
  }

  public static List<String> admittedIds() {
    return List.of(CALM_ID, FOCUS_ID);
  }

  public Candidate candidate(String id) {
    return Objects.requireNonNull(CATALOG.get(id), "unknown candidate");
  }

  public Candidate requireCurrentPin(CanonicalPin pin) {
    String ref = pin.publishedVersionRef();
    int at = ref.lastIndexOf('@');
    if (at <= 0) throw new DomainException(ErrorCode.INVALID, "C19 source pin required");
    return requireUsable(ref.substring(0, at), ref.substring(at + 1), pin.receiptSha256());
  }
}
