package com.projectb.api.http;

import static com.projectb.api.http.JourneyPathTest.check;
import static com.projectb.api.http.JourneyPathTest.drafts;
import static com.projectb.api.http.JourneyPathTest.request;
import static com.projectb.api.http.JourneyPathTest.updateBody;

import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import com.projectb.api.domain.GoalProposalAdapter;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.json.JsonMini;

/** W01–W09 coach draft workspace and C19 owner isolation. Fixture tokens are not PIAC. */
public final class JourneyCoachWorkspaceTest {
  private static final String TENANT = JourneyPathTest.TENANT_A;
  private static final String PEER = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
  private static final String GOAL = "Build a calm two-source practice";
  private static final String PROPOSALS = "/project-b/v1/tenants/" + TENANT + "/journeys/draft-proposals";
  private static final String COMMIT = PROPOSALS + "/commit";

  public static void main(String[] args) throws Exception {
    Path journal = Files.createTempDirectory("arcava-c19-workspace").resolve("journal.ndjson");
    Map<String, Actor> tokens = Map.of(
        "coach-a", new Actor(TENANT, JourneyPathTest.COACH_A, Role.COACH),
        "coach-peer", new Actor(TENANT, PEER, Role.COACH),
        "coach-b", new Actor("22222222-2222-4222-8222-222222222222", JourneyPathTest.COACH_A, Role.COACH),
        "client-a", new Actor(TENANT, JourneyPathTest.CLIENT_A, Role.CLIENT));
    Set<String> consent = Set.of(TENANT + "|" + JourneyPathTest.CLIENT_A);
    JourneyHttpServer server = JourneyHttpServer.start(journal, tokens, consent);
    try {
      int port = server.port();
      HttpResponse<String> preview = request(port, "POST", PROPOSALS, "coach-a", null, proposeBody());
      check(preview.statusCode() == 200, "preview " + preview.body());
      List<Map<String, Object>> steps = objects(data(preview.body()).get("steps"));
      steps.remove(2);
      HttpResponse<String> first = save(port, "ws-save-1", "Alpha calm draft", steps, null, null);
      HttpResponse<String> second = save(port, "ws-save-2", "Beta focus draft", steps, null, null);
      HttpResponse<String> third = save(port, "ws-save-3", "Gamma calm draft", steps, null, null);
      String idA = JsonMini.text(data(first.body()).get("draft_id"));
      String idB = JsonMini.text(data(second.body()).get("draft_id"));
      String idC = JsonMini.text(data(third.body()).get("draft_id"));
      long revA = JsonMini.integer(data(first.body()).get("revision"));

      HttpResponse<String> listed = request(port, "GET", drafts(TENANT), "coach-a", null, null);
      check(listed.statusCode() == 200, "W01 list " + listed.body());
      List<Map<String, Object>> items = objects(data(listed.body()).get("items"));
      check(items.size() == 3, "W01 three owned drafts");
      check(ids(items).equals(List.of(idA, idB, idC)), "W01 create ordinal order");
      check(items.stream().allMatch(row -> Boolean.TRUE.equals(row.get("test_only"))), "W01 test_only");
      check(!listed.body().contains("total"), "W01 no total count");

      HttpResponse<String> searched = request(port, "GET", drafts(TENANT) + "?q=calm", "coach-a", null, null);
      List<Map<String, Object>> calm = objects(data(searched.body()).get("items"));
      check(calm.size() == 2 && ids(calm).equals(List.of(idA, idC)), "W02 search before paging");

      HttpResponse<String> page1 = request(port, "GET", drafts(TENANT) + "?q=calm&limit=1", "coach-a", null, null);
      List<Map<String, Object>> firstPage = objects(data(page1.body()).get("items"));
      String cursor = JsonMini.text(data(page1.body()).get("next_cursor"));
      check(firstPage.size() == 1 && idA.equals(firstPage.get(0).get("draft_id")), "W02 first page");
      HttpResponse<String> page2 = request(port, "GET", drafts(TENANT) + "?q=calm&limit=1&cursor=" + cursor,
          "coach-a", null, null);
      List<Map<String, Object>> secondPage = objects(data(page2.body()).get("items"));
      check(secondPage.size() == 1 && idC.equals(secondPage.get(0).get("draft_id")), "W02 second page");
      check(data(page2.body()).get("next_cursor") == null, "W02 last page has no cursor");
      LinkedHashSet<String> paged = new LinkedHashSet<>();
      paged.addAll(ids(firstPage));
      paged.addAll(ids(secondPage));
      check(paged.size() == 2, "W02 no duplicate page rows");

      HttpResponse<String> opened = request(port, "GET", drafts(TENANT) + "/" + idB, "coach-a", null, null);
      check(opened.statusCode() == 200 && "Beta focus draft".equals(data(opened.body()).get("title"))
          && opened.body().contains(GoalProposalAdapter.CALM_HASH)
          && opened.body().contains(GoalProposalAdapter.FOCUS_VERSION), "W03 exact open");

      HttpResponse<String> reviewed = request(port, "POST", drafts(TENANT) + "/" + idA + "/local-review",
          "coach-a", "ws-review-1", "{\"draft_id\":\"" + idA + "\",\"expected_revision\":" + revA + "}");
      check(reviewed.statusCode() == 201 && "ACCEPTED".equals(data(reviewed.body()).get("review_state")),
          "W04 review " + reviewed.body());
      HttpResponse<String> renamed = save(port, "ws-save-1-edit", "Alpha calm renamed", steps, idA, revA);
      check("INEFFECTIVE".equals(data(renamed.body()).get("review_state")), "W04 save invalidates");
      HttpResponse<String> afterSave = request(port, "GET", drafts(TENANT) + "?review_state=INEFFECTIVE",
          "coach-a", null, null);
      check(ids(objects(data(afterSave.body()).get("items"))).equals(List.of(idA)), "W04 list matches detail");

      check(request(port, "GET", drafts(TENANT), "coach-peer", null, null).body().contains("\"items\":[]"),
          "W05 peer list empty");
      check(request(port, "GET", drafts(TENANT) + "/" + idA, "coach-peer", null, null).statusCode() == 403,
          "W05 peer GET denied");
      check(request(port, "PATCH", drafts(TENANT) + "/" + idA, "coach-peer", null,
          updateBody(JsonMini.integer(data(renamed.body()).get("revision")))).statusCode() == 403,
          "W05 peer PATCH denied");
      check(save(port, "ws-peer-save", "stolen", steps, idA,
          JsonMini.integer(data(renamed.body()).get("revision")), "coach-peer").statusCode() == 403,
          "W05 peer save denied");
      check(request(port, "POST", drafts(TENANT) + "/" + idA + "/local-review", "coach-peer", "ws-peer-review",
          "{\"draft_id\":\"" + idA + "\",\"expected_revision\":"
              + JsonMini.integer(data(renamed.body()).get("revision")) + "}").statusCode() == 403,
          "W05 peer review denied");
      check(request(port, "GET", drafts(TENANT), "coach-b", null, null).statusCode() == 403, "W05 foreign tenant");
      check(request(port, "GET", drafts(TENANT), "client-a", null, null).statusCode() == 403, "W05 client list");
      check(request(port, "GET", drafts(TENANT) + "/" + idA, "client-a", null, null).statusCode() == 403,
          "W05 client GET");

      HttpResponse<String> longQuery = request(port, "GET", drafts(TENANT) + "?q=" + "x".repeat(81),
          "coach-a", null, null);
      check(longQuery.statusCode() == 422, "W07 long query");
      HttpResponse<String> badFilter = request(port, "GET", drafts(TENANT) + "?review_state=PUBLISHED",
          "coach-a", null, null);
      check(badFilter.statusCode() == 422, "W07 invalid filter");
      HttpResponse<String> badCursor = request(port, "GET", drafts(TENANT) + "?cursor=not-hex",
          "coach-a", null, null);
      check(badCursor.statusCode() == 422, "W07 invalid cursor");
      HttpResponse<String> foreignCursor = request(port, "GET",
          drafts(TENANT) + "?q=calm&limit=1&cursor=" + cursor, "coach-peer", null, null);
      check(foreignCursor.statusCode() == 422, "W07 foreign cursor " + foreignCursor.body());
      check(!longQuery.body().contains("\"items\"") && !badFilter.body().contains("\"items\""),
          "W07 errors are not empty lists");

      server.stop();
      server = JourneyHttpServer.start(journal, tokens, consent);
      port = server.port();
      HttpResponse<String> restored = request(port, "GET", drafts(TENANT), "coach-a", null, null);
      check(ids(objects(data(restored.body()).get("items"))).equals(List.of(idA, idB, idC)), "W09 restart list");
      check("INEFFECTIVE".equals(objects(data(restored.body()).get("items")).get(0).get("review_state")),
          "W09 restart review state");
      HttpResponse<String> restoredOpen = request(port, "GET", drafts(TENANT) + "/" + idB, "coach-a", null, null);
      check("Beta focus draft".equals(data(restoredOpen.body()).get("title")), "W09 restart detail");
      check(request(port, "GET", drafts(TENANT) + "/" + idA, "coach-peer", null, null).statusCode() == 403,
          "W09 restart owner deny");
    } finally {
      server.stop();
    }
    checkLegacyC19StillDenied(tokens, consent);
    System.out.println("PASS JourneyCoachWorkspaceTest w01_list=true w02_search_page=true w03_open=true"
        + " w04_invalidate=true w05_owner_deny=true w06_historical_publish_denied=true w07_fail_closed=true"
        + " w09_restart=true test_only=true");
  }

  private static void checkLegacyC19StillDenied(Map<String, Actor> tokens, Set<String> consent) throws Exception {
    Path journal = Files.createTempDirectory("arcava-c19-ws-legacy").resolve("journal.ndjson");
    UUID draftId = UUID.fromString("c19c19c1-0000-4000-8000-000000000003");
    String calmRef = GoalProposalAdapter.CALM_ID + "@" + GoalProposalAdapter.CALM_VERSION;
    String focusRef = GoalProposalAdapter.FOCUS_ID + "@" + GoalProposalAdapter.FOCUS_VERSION;
    String stepsJson = "[{\"step_id\":\"step.c19.settle\",\"title\":\"Settle\","
        + "\"published_version_ref\":" + JsonMini.quote(calmRef)
        + ",\"receipt_sha256\":" + JsonMini.quote(GoalProposalAdapter.CALM_HASH)
        + ",\"approved\":true,\"rights_granted\":true},"
        + "{\"step_id\":\"step.c19.focus\",\"title\":\"Focus\","
        + "\"published_version_ref\":" + JsonMini.quote(focusRef)
        + ",\"receipt_sha256\":" + JsonMini.quote(GoalProposalAdapter.FOCUS_HASH)
        + ",\"approved\":true,\"rights_granted\":true}]";
    Files.writeString(journal, "{\"op\":\"create\",\"tenant_id\":" + JsonMini.quote(TENANT)
        + ",\"subject_id\":" + JsonMini.quote(JourneyPathTest.COACH_A)
        + ",\"key\":\"ws-legacy-create\",\"title\":\"Legacy unmarked C19\",\"draft_id\":"
        + JsonMini.quote(draftId.toString()) + "}\n"
        + "{\"op\":\"update\",\"tenant_id\":" + JsonMini.quote(TENANT)
        + ",\"subject_id\":" + JsonMini.quote(JourneyPathTest.COACH_A)
        + ",\"draft_id\":" + JsonMini.quote(draftId.toString())
        + ",\"expected_revision\":1,\"title\":\"Legacy unmarked C19\",\"steps\":" + stepsJson + "}\n");
    JourneyHttpServer server = JourneyHttpServer.start(journal, tokens, consent);
    try {
      int port = server.port();
      HttpResponse<String> listed = request(port, "GET", drafts(TENANT), "coach-a", null, null);
      check(listed.statusCode() == 200 && ids(objects(data(listed.body()).get("items")))
          .equals(List.of(draftId.toString())), "W06 historical C19 is listed for owner");
      check("NONE".equals(objects(data(listed.body()).get("items")).get(0).get("review_state")),
          "W06 no retroactive review");
      check(request(port, "POST", drafts(TENANT) + "/" + draftId + "/local-review", "coach-a", "ws-legacy-review",
          "{\"draft_id\":\"" + draftId + "\",\"expected_revision\":2}").statusCode() == 422,
          "W06 unmarked C19 is not reviewable");
      check(request(port, "PATCH", drafts(TENANT) + "/" + draftId, "coach-a", null, updateBody(2)).statusCode() == 200,
          "W06 owner PATCH allowed");
      String before = Files.readString(journal);
      HttpResponse<String> publish = request(port, "POST", drafts(TENANT) + "/" + draftId + "/publish",
          "coach-a", "ws-legacy-publish", "{\"expected_draft_version\":3}");
      check(publish.statusCode() == 403, "W06 publish denied after PATCH");
      check(before.equals(Files.readString(journal)), "W06 no publish journal line");
      server.stop();
      server = JourneyHttpServer.start(journal, tokens, consent);
      port = server.port();
      check(request(port, "POST", drafts(TENANT) + "/" + draftId + "/publish", "coach-a", "ws-legacy-publish-2",
          "{\"expected_draft_version\":3}").statusCode() == 403, "W06 publish denied after restart");
    } finally {
      server.stop();
    }
  }

  private static HttpResponse<String> save(int port, String key, String title, List<Map<String, Object>> steps,
                                           String draftId, Long revision) throws Exception {
    return save(port, key, title, steps, draftId, revision, "coach-a");
  }

  private static HttpResponse<String> save(int port, String key, String title, List<Map<String, Object>> steps,
                                           String draftId, Long revision, String token) throws Exception {
    Map<String, Object> body = new java.util.LinkedHashMap<>();
    body.put("learning_goal", GOAL);
    body.put("title", title);
    body.put("steps", steps);
    if (draftId != null) body.put("draft_id", draftId);
    if (revision != null) body.put("expected_revision", revision);
    return request(port, "POST", COMMIT, token, key, JsonMini.write(body));
  }

  private static String proposeBody() {
    return JsonMini.write(Map.of("learning_goal", GOAL,
        "candidate_ids", List.of(GoalProposalAdapter.CALM_ID, GoalProposalAdapter.FOCUS_ID)));
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

  private static List<String> ids(List<Map<String, Object>> items) {
    return items.stream().map(row -> JsonMini.text(row.get("draft_id"))).toList();
  }
}
