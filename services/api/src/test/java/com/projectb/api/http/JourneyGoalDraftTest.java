package com.projectb.api.http;

import static com.projectb.api.http.JourneyPathTest.check;
import static com.projectb.api.http.JourneyPathTest.drafts;
import static com.projectb.api.http.JourneyPathTest.field;
import static com.projectb.api.http.JourneyPathTest.request;
import static com.projectb.api.http.JourneyPathTest.updateBody;

import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import com.projectb.api.domain.GoalProposalAdapter;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.json.JsonMini;

/** A1–A7 local C19 goal → editable sourced draft. Fixture tokens are not PIAC. */
public final class JourneyGoalDraftTest {
  private static final String TENANT = JourneyPathTest.TENANT_A;
  private static final String GOAL = "Build a calm two-source practice";
  private static final String PROPOSALS = "/project-b/v1/tenants/" + TENANT + "/journeys/draft-proposals";
  private static final String COMMIT = PROPOSALS + "/commit";

  public static void main(String[] args) throws Exception {
    Path journal = Files.createTempDirectory("arcava-c19").resolve("journal.ndjson");
    Map<String, Actor> tokens = Map.of(
        "coach-a", new Actor(TENANT, JourneyPathTest.COACH_A, Role.COACH),
        "coach-b", new Actor("22222222-2222-4222-8222-222222222222", JourneyPathTest.COACH_A, Role.COACH),
        "client-a", new Actor(TENANT, JourneyPathTest.CLIENT_A, Role.CLIENT));
    Set<String> consent = Set.of(TENANT + "|" + JourneyPathTest.CLIENT_A);
    JourneyHttpServer server = JourneyHttpServer.start(journal, tokens, consent);
    try {
      int port = server.port();
      HttpResponse<String> created = request(port, "POST", drafts(TENANT), "coach-a", "c19-seed-draft",
          "{\"title\":\"Synthetic resilience\"}");
      check(created.statusCode() == 201, "seed draft");
      String publishedDraft = field(created.body(), "draft_id");
      check(request(port, "PATCH", drafts(TENANT) + "/" + publishedDraft, "coach-a", null, updateBody(1)).statusCode() == 200,
          "seed update");
      HttpResponse<String> published = request(port, "POST", drafts(TENANT) + "/" + publishedDraft + "/publish",
          "coach-a", "c19-seed-publish", "{\"expected_draft_version\":2}");
      check(published.statusCode() == 201, "seed publish");
      String versionId = field(published.body(), "journey_version_id");
      HttpResponse<String> assigned = request(port, "POST",
          "/project-b/v1/tenants/" + TENANT + "/clients/" + JourneyPathTest.CLIENT_A + "/assignments",
          "coach-a", "c19-seed-assign", "{\"journey_version_id\":\"" + versionId + "\"}");
      check(assigned.statusCode() == 201, "seed assign");
      String assignmentId = field(assigned.body(), "assignment_id");
      String assignedBytes = Files.readString(journal);

      HttpResponse<String> preview = request(port, "POST", PROPOSALS, "coach-a", null, proposeBody(GOAL,
          List.of(GoalProposalAdapter.CALM_ID, GoalProposalAdapter.FOCUS_ID), false));
      check(preview.statusCode() == 200, "A1 preview " + preview.body());
      Map<String, Object> previewData = data(preview.body());
      check(Boolean.TRUE.equals(previewData.get("test_only")) && "UNSAVED_PREVIEW".equals(previewData.get("publication_state")),
          "A1 preview is unpublished TEST_ONLY");
      check(!preview.body().contains("published_at"), "A1 proposal is not a CT-ARC-002 publication");
      List<Map<String, Object>> steps = objects(previewData.get("steps"));
      check(steps.size() == 3, "A1 three ordered steps");
      check(source(steps.get(0)).get("candidate_id").equals(GoalProposalAdapter.CALM_ID)
          && source(steps.get(1)).get("candidate_id").equals(GoalProposalAdapter.FOCUS_ID)
          && source(steps.get(2)).get("candidate_id").equals(GoalProposalAdapter.CALM_ID), "A1 uses exactly two candidates");
      check(GoalProposalAdapter.CALM_HASH.equals(source(steps.get(0)).get("content_hash"))
          && GoalProposalAdapter.FOCUS_HASH.equals(source(steps.get(1)).get("content_hash")), "A1 pins hashes");
      check(assignedBytes.equals(Files.readString(journal)), "A1 preview does not persist");

      steps.get(0).put("title", "Settle slowly");
      Map<String, Object> first = steps.get(0);
      steps.set(0, steps.get(1));
      steps.set(1, first);
      steps.remove(2);
      HttpResponse<String> saved = request(port, "POST", COMMIT, "coach-a", "c19-save-1",
          commitBody(GOAL, "Calm practice draft", steps, null, null));
      check(saved.statusCode() == 201, "A2 save " + saved.body());
      Map<String, Object> savedData = data(saved.body());
      check("draft".equals(savedData.get("status")) && "DRAFT".equals(savedData.get("publication_state")), "A2 stays draft");
      List<Map<String, Object>> savedSteps = objects(savedData.get("steps"));
      check(savedSteps.size() == 2 && "Reset attention".equals(savedSteps.get(0).get("title"))
          && "Settle slowly".equals(savedSteps.get(1).get("title")), "A2 edited title order remove");
      String draftId = JsonMini.text(savedData.get("draft_id"));
      long revision = JsonMini.integer(savedData.get("revision"));
      HttpResponse<String> sameSave = request(port, "POST", COMMIT, "coach-a", "c19-save-1",
          commitBody(GOAL, "Calm practice draft", steps, null, null));
      check(sameSave.statusCode() == 201 && draftId.equals(field(sameSave.body(), "draft_id"))
          && Long.toString(revision).equals(field(sameSave.body(), "revision")), "A5 same-key save keeps revision");

      HttpResponse<String> stale = request(port, "POST", COMMIT, "coach-a", "c19-stale",
          commitBody(GOAL, "Calm practice draft", steps, draftId, 1L));
      check(stale.statusCode() == 409 && stale.body().contains("STALE_REVISION"), "A5 stale revision " + stale.body());

      String afterSave = Files.readString(journal);
      check(afterSave.contains(assignmentId) && afterSave.contains("\"op\":\"assign\""), "A6 assignment retained");
      check(!afterSave.substring(assignedBytes.length()).contains("\"op\":\"publish\""), "A6 save does not publish");
      check(!afterSave.substring(assignedBytes.length()).contains("\"op\":\"assign\""), "A6 save does not assign");

      HttpResponse<String> loaded = request(port, "GET", drafts(TENANT) + "/" + draftId, "coach-a", null, null);
      check(loaded.statusCode() == 200, "A3 load " + loaded.body());
      check("Settle slowly".equals(objects(data(loaded.body()).get("steps")).get(1).get("title")), "A3 titles persist");
      check(loaded.body().contains(GoalProposalAdapter.CALM_HASH)
          && loaded.body().contains(GoalProposalAdapter.FOCUS_HASH), "A3 hashes persist");

      server.stop();
      server = JourneyHttpServer.start(journal, tokens, consent);
      port = server.port();
      HttpResponse<String> restored = request(port, "GET", drafts(TENANT) + "/" + draftId, "coach-a", null, null);
      check(restored.statusCode() == 200 && draftId.equals(field(restored.body(), "draft_id"))
          && Long.toString(revision).equals(field(restored.body(), "revision")), "A3 restart revision");
      check(restored.body().contains(GoalProposalAdapter.CALM_VERSION)
          && restored.body().contains(GoalProposalAdapter.FOCUS_HASH), "A3 restart pins");
      check("Settle slowly".equals(objects(data(restored.body()).get("steps")).get(1).get("title")), "A3 restart titles");

      deniedPreview(port, List.of("unknown.source"), "INVALID");
      deniedPreview(port, List.of(GoalProposalAdapter.CALM_ID, GoalProposalAdapter.WITHDRAWN_ID), "WITHDRAWN");
      deniedPreview(port, List.of(GoalProposalAdapter.CALM_ID, GoalProposalAdapter.PERSONAL_ID), "UNPUBLISHED_CANONICAL");
      deniedPreview(port, List.of(GoalProposalAdapter.CALM_ID, GoalProposalAdapter.REVOKED_ID), "UNPUBLISHED_CANONICAL");
      List<Map<String, Object>> badHash = copySteps(savedSteps);
      source(badHash.get(0)).put("content_hash", GoalProposalAdapter.CALM_HASH);
      HttpResponse<String> manipulated = request(port, "POST", COMMIT, "coach-a", "c19-bad-hash",
          commitBody(GOAL, "Calm practice draft", badHash, draftId, revision));
      check(manipulated.statusCode() == 422 && manipulated.body().contains("UNPUBLISHED_CANONICAL"),
          "A4 manipulated hash " + manipulated.body());
      List<Map<String, Object>> wrongVersion = copySteps(savedSteps);
      source(wrongVersion.get(0)).put("version", "not-the-pin");
      HttpResponse<String> versionDenied = request(port, "POST", COMMIT, "coach-a", "c19-bad-version",
          commitBody(GOAL, "Calm practice draft", wrongVersion, draftId, revision));
      check(versionDenied.statusCode() == 422 && versionDenied.body().contains("INVALID"),
          "A4 wrong version " + versionDenied.body());

      HttpResponse<String> adapterFail = request(port, "POST", PROPOSALS, "coach-a", null, proposeBody(GOAL,
          List.of(GoalProposalAdapter.CALM_ID, GoalProposalAdapter.FOCUS_ID), true));
      check(adapterFail.statusCode() == 503 && adapterFail.body().contains("ADAPTER_UNAVAILABLE")
          && adapterFail.body().contains("\"retryable\":true"), "A7 retryable adapter error " + adapterFail.body());
      HttpResponse<String> stillThere = request(port, "GET", drafts(TENANT) + "/" + draftId, "coach-a", null, null);
      check(stillThere.statusCode() == 200 && Long.toString(revision).equals(field(stillThere.body(), "revision"))
          && "Settle slowly".equals(objects(data(stillThere.body()).get("steps")).get(1).get("title")),
          "A7 saved draft survives adapter failure");
      check(request(port, "GET",
          "/project-b/v1/tenants/" + TENANT + "/journeys/versions/" + versionId, "coach-a", null, null)
          .statusCode() == 200, "A6 published version unchanged");

      String beforeReview = Files.readString(journal);
      HttpResponse<String> c19PublishBefore = request(port, "POST",
          drafts(TENANT) + "/" + draftId + "/publish", "coach-a", "c19-review-publish-before",
          "{\"expected_draft_version\":" + revision + "}");
      check(c19PublishBefore.statusCode() == 403 && c19PublishBefore.body().contains("FORBIDDEN")
          && !c19PublishBefore.body().contains("\"data\""), "R06 C19 publish denied before review");
      check(beforeReview.equals(Files.readString(journal)), "R06 before-review publish leaves journal unchanged");

      HttpResponse<String> loadedForReview = request(port, "GET", drafts(TENANT) + "/" + draftId, "coach-a", null, null);
      Map<String, Object> loadedReview = data(loadedForReview.body());
      String digest = JsonMini.text(loadedReview.get("digest"));
      check(digest != null && digest.matches("[0-9a-f]{64}"), "R01 server digest");
      check("NONE".equals(loadedReview.get("review_state")), "R01 no retroactive approval");
      check("C19_GOAL_DRAFT".equals(loadedReview.get("origin")), "R01 typed C19 origin");
      check("DRAFT".equals(loadedReview.get("publication_state")), "R01 stays draft");

      HttpResponse<String> unknownField = request(port, "POST", localReview(TENANT, draftId), "coach-a",
          "c19-review-unknown", "{\"draft_id\":\"" + draftId + "\",\"expected_revision\":" + revision
              + ",\"digest\":\"" + digest + "\"}");
      check(unknownField.statusCode() == 422 && unknownField.body().contains("INVALID"),
          "R05 unknown digest field " + unknownField.body());
      check(request(port, "POST", localReview(TENANT, draftId), "client-a", "c19-review-client",
          reviewBody(draftId, revision)).statusCode() == 403, "R05 client denied");
      check(request(port, "POST", localReview(TENANT, draftId), "coach-b", "c19-review-tenant",
          reviewBody(draftId, revision)).statusCode() == 403, "R05 wrong tenant denied");
      check(request(port, "POST", localReview(TENANT, draftId), null, "c19-review-anon",
          reviewBody(draftId, revision)).statusCode() == 401, "R05 missing bearer");
      check(beforeReview.equals(Files.readString(journal)), "R05 denials do not mutate journal");

      HttpResponse<String> staleReview = request(port, "POST", localReview(TENANT, draftId), "coach-a",
          "c19-review-stale", reviewBody(draftId, 1L));
      check(staleReview.statusCode() == 409 && staleReview.body().contains("STALE_REVISION"),
          "R04 stale expected_revision " + staleReview.body());

      HttpResponse<String> reviewed = request(port, "POST", localReview(TENANT, draftId), "coach-a",
          "c19-review-1", reviewBody(draftId, revision));
      check(reviewed.statusCode() == 201, "R01 review " + reviewed.body());
      Map<String, Object> reviewedData = data(reviewed.body());
      check("ACCEPTED".equals(reviewedData.get("review_state")), "R01 accepted");
      check(digest.equals(reviewedData.get("digest")), "R01 digest bound");
      check(JourneyPathTest.COACH_A.equals(JsonMini.object(reviewedData.get("review_receipt")).get("reviewer_id")),
          "R01 reviewer is server actor");
      check("DRAFT".equals(reviewedData.get("publication_state")), "R01 review is not publish");
      String afterReview = Files.readString(journal);
      check(afterReview.contains("\"op\":\"c19_local_review\""), "R01 review persisted");
      check(!afterReview.substring(assignedBytes.length()).contains("\"op\":\"publish\""),
          "R01 review does not publish");
      check(!afterReview.substring(assignedBytes.length()).contains("\"op\":\"assign\""),
          "R01 review does not assign");

      HttpResponse<String> sameReview = request(port, "POST", localReview(TENANT, draftId), "coach-a",
          "c19-review-1", reviewBody(draftId, revision));
      check(sameReview.statusCode() == 201 && digest.equals(field(sameReview.body(), "digest"))
          && "ACCEPTED".equals(data(sameReview.body()).get("review_state")), "R04 same key idempotent");
      check(afterReview.equals(Files.readString(journal)), "R04 idempotent review adds no journal line");

      HttpResponse<String> alteredKey = request(port, "POST", localReview(TENANT, draftId), "coach-a",
          "c19-review-1", reviewBody(draftId, revision + 1));
      check(alteredKey.statusCode() == 409 && alteredKey.body().contains("IDEMPOTENCY_CONFLICT"),
          "R04 same key altered body " + alteredKey.body());
      check(afterReview.equals(Files.readString(journal)), "R04 conflict leaves journal unchanged");

      HttpResponse<String> c19PublishAfter = request(port, "POST",
          drafts(TENANT) + "/" + draftId + "/publish", "coach-a", "c19-review-publish-after",
          "{\"expected_draft_version\":" + revision + "}");
      check(c19PublishAfter.statusCode() == 403 && c19PublishAfter.body().contains("FORBIDDEN"),
          "R06 C19 publish denied after review");
      check(afterReview.equals(Files.readString(journal)), "R06 after-review publish leaves journal unchanged");
      check(request(port, "GET",
          "/project-b/v1/tenants/" + TENANT + "/journeys/versions/" + versionId, "coach-a", null, null)
          .statusCode() == 200, "R06 legacy published version remains");

      server.stop();
      server = JourneyHttpServer.start(journal, tokens, consent);
      port = server.port();
      HttpResponse<String> restoredReview = request(port, "GET", drafts(TENANT) + "/" + draftId, "coach-a", null, null);
      Map<String, Object> restoredReviewData = data(restoredReview.body());
      check(restoredReview.statusCode() == 200 && "ACCEPTED".equals(restoredReviewData.get("review_state"))
          && digest.equals(restoredReviewData.get("digest"))
          && Long.toString(revision).equals(field(restoredReview.body(), "revision")),
          "R02 restart keeps accepted receipt");
      check(restoredReview.body().contains(GoalProposalAdapter.CALM_HASH)
          && restoredReview.body().contains(GoalProposalAdapter.FOCUS_HASH), "R02 source pins preserved");

      HttpResponse<String> renamed = request(port, "POST", COMMIT, "coach-a", "c19-review-rename",
          commitBody(GOAL, "Changed after review", savedSteps, draftId, revision));
      check(renamed.statusCode() == 201, "R03 title change saves " + renamed.body());
      long newRevision = JsonMini.integer(data(renamed.body()).get("revision"));
      check(newRevision != revision && "INEFFECTIVE".equals(data(renamed.body()).get("review_state")),
          "R03 saved change makes review ineffective");
      check(!digest.equals(data(renamed.body()).get("digest")), "R03 digest changes with title");
      HttpResponse<String> publishStaleReview = request(port, "POST",
          drafts(TENANT) + "/" + draftId + "/publish", "coach-a", "c19-review-publish-changed",
          "{\"expected_draft_version\":" + newRevision + "}");
      check(publishStaleReview.statusCode() == 403, "R06 still denied after invalidating edit");
    } finally {
      server.stop();
    }
    System.out.println("PASS JourneyGoalDraftTest a1_two_candidates=true a2_edit_save=true a3_restart=true"
        + " a4_source_denials=true a5_revision=true a6_no_publish_assign=true a7_adapter_error=true"
        + " r01_review=true r02_restart=true r03_invalidate=true r04_idempotency=true r05_auth=true"
        + " r06_c19_publish_denied=true test_only=true");
  }

  private static void deniedPreview(int port, List<String> ids, String code) throws Exception {
    HttpResponse<String> result = request(port, "POST", PROPOSALS, "coach-a", null, proposeBody(GOAL, ids, false));
    check(result.statusCode() == 422 && result.body().contains(code),
        "A4 " + ids + " " + result.statusCode() + " " + result.body());
  }

  private static String proposeBody(String goal, List<String> ids, boolean forceError) {
    Map<String, Object> body = new java.util.LinkedHashMap<>();
    body.put("learning_goal", goal);
    body.put("candidate_ids", ids);
    if (forceError) body.put("force_adapter_error", true);
    return JsonMini.write(body);
  }

  private static String localReview(String tenant, String draftId) {
    return drafts(tenant) + "/" + draftId + "/local-review";
  }

  private static String reviewBody(String draftId, long revision) {
    return "{\"draft_id\":\"" + draftId + "\",\"expected_revision\":" + revision + "}";
  }

  private static String commitBody(String goal, String title, List<Map<String, Object>> steps,
                                   String draftId, Long revision) {
    Map<String, Object> body = new java.util.LinkedHashMap<>();
    body.put("learning_goal", goal);
    body.put("title", title);
    body.put("steps", steps);
    if (draftId != null) body.put("draft_id", draftId);
    if (revision != null) body.put("expected_revision", revision);
    return JsonMini.write(body);
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> data(String json) {
    return JsonMini.object(JsonMini.object(JsonMini.parse(json)).get("data"));
  }

  @SuppressWarnings("unchecked")
  private static List<Map<String, Object>> objects(Object value) {
    if (!(value instanceof List<?> list)) throw new AssertionError("list required");
    List<Map<String, Object>> rows = new ArrayList<>();
    for (Object item : list) rows.add((Map<String, Object>) item);
    return rows;
  }

  @SuppressWarnings("unchecked")
  private static Map<String, Object> source(Map<String, Object> step) {
    return (Map<String, Object>) step.get("source");
  }

  private static List<Map<String, Object>> copySteps(List<Map<String, Object>> steps) {
    return objects(JsonMini.parse(JsonMini.write(steps)));
  }
}
