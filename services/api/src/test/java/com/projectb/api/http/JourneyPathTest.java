package com.projectb.api.http;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;
import java.util.Set;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.json.JsonMini;

/** Local persisted coach and client path. Fixture tokens are not PIAC. */
public final class JourneyPathTest {
  private static final String TENANT_A = "11111111-1111-4111-8111-111111111111";
  private static final String TENANT_B = "22222222-2222-4222-8222-222222222222";
  private static final String COACH_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  private static final String COACH_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
  private static final String CLIENT_A = "33333333-3333-4333-8333-333333333333";
  private static final String CLIENT_OTHER = "44444444-4444-4444-8444-444444444444";
  private static final String CLIENT_NO_CONSENT = "55555555-5555-4555-8555-555555555555";
  private static final String STEP = "66666666-6666-4666-8666-666666666666";
  private static final String SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
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
      server.stop();
      server = JourneyHttpServer.start(journal, tokens, consent);
      port = server.port();
      HttpResponse<String> restored = request(port, "GET", clientVersion(TENANT_A, CLIENT_A, assignmentId), "client-a", null, null);
      check(restored.statusCode() == 200 && versionId.equals(field(restored.body(), "journey_version_id")), "restart " + restored.body());
      check(request(port, "GET", clientVersion(TENANT_B, CLIENT_A, assignmentId), "client-a", null, null).statusCode() == 403, "client tenant denied");
      check(request(port, "GET", clientVersion(TENANT_A, CLIENT_OTHER, assignmentId), "client-other", null, null).statusCode() == 403, "other client denied");
      HttpResponse<String> withdrawn = request(port, "POST",
          "/project-b/v1/tenants/" + TENANT_A + "/journeys/versions/" + versionId + "/withdraw",
          "coach-a", null, "{}");
      check(withdrawn.statusCode() == 200 && "revoked".equals(field(withdrawn.body(), "status")), "withdrawn " + withdrawn.body());
      HttpResponse<String> replay = request(port, "POST", assignments(TENANT_A, CLIENT_A), "coach-a", "assign-1",
          "{\"journey_version_id\":\"" + versionId + "\"}");
      check(replay.statusCode() == 422 && replay.body().contains("WITHDRAWN"), "replay " + replay.body());
      check(request(port, "GET", clientVersion(TENANT_A, CLIENT_A, assignmentId), "client-a", null, null).statusCode() == 422, "client read closed");
      HttpResponse<String> publishReplay = request(port, "POST", drafts(TENANT_A) + "/" + draftId + "/publish",
          "coach-a", "publish-1", "{\"expected_draft_version\":2}");
      check(publishReplay.statusCode() == 201 && "revoked".equals(field(publishReplay.body(), "status")), "publish replay " + publishReplay.body());
    } finally {
      server.stop();
    }
    JourneyHttpServer again = JourneyHttpServer.start(journal, tokens, consent);
    try {
      HttpResponse<String> closed = request(again.port(), "GET", clientVersion(TENANT_A, CLIENT_A, assignmentId), "client-a", null, null);
      check(closed.statusCode() == 422 && closed.body().contains("WITHDRAWN"), "withdrawal survived restart " + closed.body());
    } finally {
      again.stop();
    }
    System.out.println("PASS JourneyPathTest persisted_http=true restart=true tenant_isolation=true consent_gate=true withdrawal=true piac=not_connected kdb=not_connected");
  }

  private static String drafts(String tenant) {
    return "/project-b/v1/tenants/" + tenant + "/journeys/drafts";
  }

  private static String assignments(String tenant, String client) {
    return "/project-b/v1/tenants/" + tenant + "/clients/" + client + "/assignments";
  }

  private static String clientVersion(String tenant, String client, String assignment) {
    return assignments(tenant, client) + "/" + assignment + "/version";
  }

  private static String updateBody(long revision) {
    return "{\"title\":\"Synthetic resilience\",\"expected_revision\":" + revision
        + ",\"phases\":[{\"title\":\"Practice\",\"steps\":[{\"step_id\":\"" + STEP
        + "\",\"title\":\"Breathing\",\"canonical_refs\":[{\"ref_type\":\"protocol\",\"ref_id\":\"kdb:protocol:published-version-v1\",\"version\":\""
        + SHA + "\"}],\"acceptance\":{\"receipt_sha256\":\"" + SHA + "\",\"approved\":true,\"rights_granted\":true}}]}]}";
  }

  private static HttpResponse<String> request(int port, String method, String path, String token,
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

  private static String field(String json, String name) {
    Map<String, Object> data = JsonMini.object(JsonMini.object(JsonMini.parse(json)).get("data"));
    Object value = data.get(name);
    if (value instanceof Long number) return Long.toString(number);
    return JsonMini.text(value);
  }

  private static void check(boolean condition, String label) {
    if (!condition) throw new AssertionError(label);
  }
}
