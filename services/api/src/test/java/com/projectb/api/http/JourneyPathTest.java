package com.projectb.api.http;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Arrays;
import java.util.Map;
import java.util.Set;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.json.JsonMini;

/** Local persisted coach and client path. Fixture tokens are not PIAC. */
public final class JourneyPathTest {
  static final String TENANT_A = "11111111-1111-4111-8111-111111111111";
  private static final String TENANT_B = "22222222-2222-4222-8222-222222222222";
  static final String COACH_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  private static final String COACH_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
  static final String CLIENT_A = "33333333-3333-4333-8333-333333333333";
  private static final String CLIENT_OTHER = "44444444-4444-4444-8444-444444444444";
  private static final String CLIENT_NO_CONSENT = "55555555-5555-4555-8555-555555555555";
  static final String STEP = "66666666-6666-4666-8666-666666666666";
  private static final String SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  private static final String PA05_SOURCE = """
      {"schema_version":1,"variant":"KDB_PROTOCOL_VERSION",
       "protocol_id":"05000000-0000-4000-8000-000000000009",
       "protocol_version_id":"05000000-0000-4000-8000-000000000010",
       "owning_module_id":"05000000-0000-4000-8000-000000000013",
       "taxonomy_version_id":"05000000-0000-4000-8000-000000000014","relation_ids":[]}
      """;
  private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

  public static void main(String[] args) throws Exception {
    Path journal = Files.createTempDirectory("arcava-journey").resolve("journal.ndjson");
    Map<String, Actor> tokens = Map.of(
        "coach-a", new Actor(TENANT_A, COACH_A, Role.COACH),
        "coach-b", new Actor(TENANT_B, COACH_B, Role.COACH),
        "client-a", new Actor(TENANT_A, CLIENT_A, Role.CLIENT),
        "client-other", new Actor(TENANT_A, CLIENT_OTHER, Role.CLIENT));
    Set<String> consent = Set.of(TENANT_A + "|" + CLIENT_A, TENANT_A + "|" + CLIENT_OTHER);
    String draftId = "";
    String versionId = "";
    String assignmentId = "";
    JourneyHttpServer server = JourneyHttpServer.start(journal, tokens, consent);
    try {
      int port = server.port();
      check(request(port, "GET", "/project-b/v1/health", null, null, null).statusCode() == 200, "ready");
      HttpResponse<String> created = request(port, "POST", drafts(TENANT_A), "coach-a", "create-1",
          "{\"title\":\"Synthetic resilience\"}");
      check(created.statusCode() == 201, "create status " + created.statusCode() + " " + created.body());
      draftId = field(created.body(), "draft_id");
      HttpResponse<String> denied = request(port, "PATCH", drafts(TENANT_A) + "/" + draftId, "coach-b", null, updateBody(1));
      check(denied.statusCode() == 403, "cross-tenant coach denied " + denied.statusCode());
      HttpResponse<String> updated = request(port, "PATCH", drafts(TENANT_A) + "/" + draftId, "coach-a", null, updateBody(1));
      check(updated.statusCode() == 200 && "2".equals(field(updated.body(), "revision")), "revision " + updated.body());
      HttpResponse<String> published = request(port, "POST", drafts(TENANT_A) + "/" + draftId + "/publish",
          "coach-a", "publish-1", "{\"expected_draft_version\":2}");
      check(published.statusCode() == 201 && "published".equals(field(published.body(), "status")), "published " + published.body());
      versionId = field(published.body(), "journey_version_id");
      HttpResponse<String> noConsent = request(port, "POST", assignments(TENANT_A, CLIENT_NO_CONSENT), "coach-a", "assign-no",
          "{\"journey_version_id\":\"" + versionId + "\",\"consent_verified\":true}");
      check(noConsent.statusCode() == 422 && noConsent.body().contains("CONSENT_REQUIRED"), "body consent is not authority");
      HttpResponse<String> assigned = request(port, "POST", assignments(TENANT_A, CLIENT_A), "coach-a", "assign-1",
          "{\"journey_version_id\":\"" + versionId + "\"}");
      check(assigned.statusCode() == 201, "assignment " + assigned.body());
      assignmentId = field(assigned.body(), "assignment_id");
      byte[] assignedBytes = Files.readAllBytes(journal);
      String stepPath = clientStep(TENANT_A, CLIENT_A, assignmentId, STEP);
      checkStep(request(port, "GET", stepPath, "client-a", null, null), versionId);
      checkStep(request(port, "GET", stepPath, "client-a", null, null), versionId);
      checkUnchanged(journal, assignedBytes, "repeated open");
      server.stop();
      server = JourneyHttpServer.start(journal, tokens, consent);
      port = server.port();
      HttpResponse<String> restored = request(port, "GET", clientVersion(TENANT_A, CLIENT_A, assignmentId), "client-a", null, null);
      check(restored.statusCode() == 200 && versionId.equals(field(restored.body(), "journey_version_id")), "restart " + restored.body());
      checkStep(request(port, "GET", stepPath, "client-a", null, null), versionId);
      HttpResponse<String> sameAssignment = request(port, "POST", assignments(TENANT_A, CLIENT_A), "coach-a", "assign-1",
          "{\"journey_version_id\":\"" + versionId + "\"}");
      check(sameAssignment.statusCode() == 201 && assignmentId.equals(field(sameAssignment.body(), "assignment_id")), "assignment replay identity");
      HttpResponse<String> sameVersion = request(port, "POST", drafts(TENANT_A) + "/" + draftId + "/publish",
          "coach-a", "publish-1", "{\"expected_draft_version\":2}");
      check(sameVersion.statusCode() == 201 && versionId.equals(field(sameVersion.body(), "journey_version_id")), "publish replay identity");
      denied(port, clientStep(TENANT_B, CLIENT_A, assignmentId, STEP), "client-a", 403, "FORBIDDEN");
      denied(port, clientStep(TENANT_A, CLIENT_OTHER, assignmentId, STEP), "client-other", 403, "FORBIDDEN");
      denied(port, clientStep(TENANT_A, CLIENT_A, versionId, STEP), "client-a", 404, "NOT_FOUND");
      denied(port, clientStep(TENANT_A, CLIENT_A, assignmentId, CLIENT_OTHER), "client-a", 404, "NOT_FOUND");
      denied(port, stepPath, "coach-a", 403, "FORBIDDEN");
      denied(port, stepPath + "?protocol_version_id=latest", "client-a", 422, "INVALID");
      checkUnchanged(journal, assignedBytes, "restart, replays and denied reads");
      checkBadSources(port, journal);
      check(request(port, "GET", clientVersion(TENANT_B, CLIENT_A, assignmentId), "client-a", null, null).statusCode() == 403, "client tenant denied");
      check(request(port, "GET", clientVersion(TENANT_A, CLIENT_OTHER, assignmentId), "client-other", null, null).statusCode() == 403, "other client denied");
      HttpResponse<String> withdrawn = request(port, "POST",
          "/project-b/v1/tenants/" + TENANT_A + "/journeys/versions/" + versionId + "/withdraw",
          "coach-a", null, "{}");
      check(withdrawn.statusCode() == 200 && "revoked".equals(field(withdrawn.body(), "status")), "withdrawn " + withdrawn.body());
      byte[] withdrawnBytes = Files.readAllBytes(journal);
      denied(port, stepPath, "client-a", 422, "WITHDRAWN");
      HttpResponse<String> replay = request(port, "POST", assignments(TENANT_A, CLIENT_A), "coach-a", "assign-1",
          "{\"journey_version_id\":\"" + versionId + "\"}");
      check(replay.statusCode() == 422 && replay.body().contains("WITHDRAWN"), "replay " + replay.body());
      check(request(port, "GET", clientVersion(TENANT_A, CLIENT_A, assignmentId), "client-a", null, null).statusCode() == 422, "client read closed");
      HttpResponse<String> publishReplay = request(port, "POST", drafts(TENANT_A) + "/" + draftId + "/publish",
          "coach-a", "publish-1", "{\"expected_draft_version\":2}");
      check(publishReplay.statusCode() == 201 && "revoked".equals(field(publishReplay.body(), "status")), "publish replay " + publishReplay.body());
      checkUnchanged(journal, withdrawnBytes, "withdrawn reads and replays");
    } finally {
      server.stop();
    }
    JourneyHttpServer again = JourneyHttpServer.start(journal, tokens, consent);
    try {
      byte[] before = Files.readAllBytes(journal);
      denied(again.port(), clientStep(TENANT_A, CLIENT_A, assignmentId, STEP), "client-a", 422, "WITHDRAWN");
      HttpResponse<String> closed = request(again.port(), "GET", clientVersion(TENANT_A, CLIENT_A, assignmentId), "client-a", null, null);
      check(closed.statusCode() == 422 && closed.body().contains("WITHDRAWN"), "withdrawal survived restart " + closed.body());
      checkUnchanged(journal, before, "withdrawn reads after restart");
    } finally {
      again.stop();
    }
    System.out.println("PASS JourneyPathTest persisted_http=true restart=true tenant_isolation=true consent_gate=true withdrawal=true piac=not_connected kdb=not_connected");
    System.out.println("PASS ARCAVA08 assigned_step=true exact_pa05_pin=true restart=true foreign_and_unassigned_denied=true"
        + " wrong_step_denied=true missing_and_swapped_pin_denied=true withdrawal_replayed=true idempotency_conflict=true journal_bytes_preserved=true");
  }

  static String drafts(String tenant) {
    return "/project-b/v1/tenants/" + tenant + "/journeys/drafts";
  }

  private static String assignments(String tenant, String client) {
    return "/project-b/v1/tenants/" + tenant + "/clients/" + client + "/assignments";
  }

  private static String clientVersion(String tenant, String client, String assignment) {
    return assignments(tenant, client) + "/" + assignment + "/version";
  }

  static String updateBody(long revision) {
    return updateBody(revision, PA05_SOURCE);
  }

  private static String updateBody(long revision, String source) {
    return "{\"title\":\"Synthetic resilience\",\"expected_revision\":" + revision
        + ",\"phases\":[{\"title\":\"Practice\",\"steps\":[{\"step_id\":\"" + STEP
        + "\",\"title\":\"Breathing\",\"canonical_refs\":[{\"ref_type\":\"protocol\",\"ref_id\":\"kdb:protocol:published-version-v1\",\"version\":\""
        + SHA + "\"}],\"acceptance\":{\"receipt_sha256\":\"" + SHA + "\",\"approved\":true,\"rights_granted\":true}}]}],"
        + "\"producer_phases\":[{\"steps\":[{\"step_id\":\"" + STEP + "\""
        + (source == null ? "" : ",\"source_ref\":" + source) + "}]}]}";
  }

  private static String clientStep(String tenant, String client, String assignment, String step) {
    return clientVersion(tenant, client, assignment) + "/steps/" + step;
  }

  private static void checkStep(HttpResponse<String> response, String version) {
    check(response.statusCode() == 200, "open status " + response.body());
    Map<String, Object> data = JsonMini.object(JsonMini.object(JsonMini.parse(response.body())).get("data"));
    check(version.equals(data.get("journey_version_id")) && STEP.equals(data.get("step_id")), "exact version and step");
    check(JsonMini.parse(PA05_SOURCE).equals(data.get("source_ref")), "complete exact PA05 source_ref");
    check("TEST_LOOPBACK_ONLY".equals(data.get("profile")), "fixture profile");
  }

  private static void denied(int port, String path, String token, int status, String code) throws Exception {
    HttpResponse<String> result = request(port, "GET", path, token, null, null);
    Map<String, Object> body = JsonMini.object(JsonMini.parse(result.body()));
    check(result.statusCode() == status && code.equals(JsonMini.object(body.get("error")).get("code"))
        && !body.containsKey("data"), "denial " + path + " " + result.statusCode() + " " + result.body());
  }

  private static void checkUnchanged(Path journal, byte[] before, String operation) throws Exception {
    check(Arrays.equals(before, Files.readAllBytes(journal)), operation + " must preserve journal bytes");
  }

  private static void checkBadSources(int port, Path journal) throws Exception {
    String[] sources = {null, PA05_SOURCE.replace("000000000010", "000000000099"),
        PA05_SOURCE.replace("000000000013", "000000000099"), PA05_SOURCE.replace("000000000014", "000000000099")};
    for (int i = 0; i < sources.length; i++) {
      String draft = field(request(port, "POST", drafts(TENANT_A), "coach-a", "bad-create-" + i,
          "{\"title\":\"Source rejection fixture\"}").body(), "draft_id");
      check(request(port, "PATCH", drafts(TENANT_A) + "/" + draft, "coach-a", null,
          updateBody(1, sources[i])).statusCode() == 200, "store untrusted source candidate");
      String version = field(request(port, "POST", drafts(TENANT_A) + "/" + draft + "/publish", "coach-a",
          "bad-publish-" + i, "{\"expected_draft_version\":2}").body(), "journey_version_id");
      String intent = "{\"journey_version_id\":\"" + version + "\"}";
      byte[] beforeConflict = Files.readAllBytes(journal);
      HttpResponse<String> conflict = request(port, "POST", assignments(TENANT_A, CLIENT_A), "coach-a", "assign-1", intent);
      check(conflict.statusCode() == 409 && conflict.body().contains("IDEMPOTENCY_CONFLICT"), "changed assignment intent denied");
      checkUnchanged(journal, beforeConflict, "assignment conflict");
      String assignment = field(request(port, "POST", assignments(TENANT_A, CLIENT_A), "coach-a", "bad-assign-" + i,
          intent).body(), "assignment_id");
      byte[] beforeOpen = Files.readAllBytes(journal);
      denied(port, clientStep(TENANT_A, CLIENT_A, assignment, STEP), "client-a", 422, "UNPUBLISHED_CANONICAL");
      checkUnchanged(journal, beforeOpen, "mismatched step source denial");
    }
  }

  static HttpResponse<String> request(int port, String method, String path, String token,
                                             String idempotency, String body) throws Exception {
    HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
        .timeout(Duration.ofSeconds(3))
        .header("X-Correlation-Id", "77777777-7777-4777-8777-777777777777");
    if (token != null) builder.header("Authorization", "Bearer " + token);
    if (idempotency != null) builder.header("Idempotency-Key", idempotency);
    if (body == null) builder.method(method, HttpRequest.BodyPublishers.noBody());
    else builder.method(method, HttpRequest.BodyPublishers.ofString(body)).header("Content-Type", "application/json");
    return HTTP.send(builder.build(), HttpResponse.BodyHandlers.ofString());
  }

  static String field(String json, String name) {
    Map<String, Object> data = JsonMini.object(JsonMini.object(JsonMini.parse(json)).get("data"));
    Object value = data.get(name);
    if (value instanceof Long number) return Long.toString(number);
    return JsonMini.text(value);
  }

  static void check(boolean condition, String label) {
    if (!condition) throw new AssertionError(label);
  }
}
