package com.projectb.api.http;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.json.JsonMini;

/** Journal-backed producer reads. Fixture tokens and pins are not PIAC or KDB. */
public final class JourneyProducerTest {
  private static final String TENANT_A = "11111111-1111-4111-8111-111111111111";
  private static final String TENANT_B = "22222222-2222-4222-8222-222222222222";
  private static final String COACH_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  private static final String COACH_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
  private static final String CLIENT_A = "33333333-3333-4333-8333-333333333333";
  private static final String CLIENT_OTHER = "44444444-4444-4444-8444-444444444444";
  private static final String STEP = "66666666-6666-4666-8666-666666666666";
  private static final String SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
  private static final List<String> CAPTURED = new ArrayList<>();
  private static final List<String> REQUESTS = new ArrayList<>();

  public static void main(String[] args) throws Exception {
    Path dir = Files.createTempDirectory("arcava-producer");
    Path journal = dir.resolve("journal.ndjson");
    Map<String, Actor> tokens = Map.of(
        "coach-a", new Actor(TENANT_A, COACH_A, Role.COACH),
        "coach-b", new Actor(TENANT_B, COACH_B, Role.COACH),
        "client-a", new Actor(TENANT_A, CLIENT_A, Role.CLIENT),
        "client-other", new Actor(TENANT_A, CLIENT_OTHER, Role.CLIENT));
    Set<String> consent = Set.of(TENANT_A + "|" + CLIENT_A);
    JourneyHttpServer server = JourneyHttpServer.start(journal, tokens, consent);
    String versionId;
    String journeyId;
    String decisionId;
    String bindingId;
    try {
      int port = server.port();
      String draftId = field(call(port, "POST", drafts(), "coach-a", "create-1", "{\"title\":\"Synthetic resilience\"}", null).body(), "draft_id");
      HttpResponse<String> updated = call(port, "PATCH", drafts() + "/" + draftId, "coach-a", null, updateBody(), null);
      check(updated.statusCode() == 200, "update " + updated.body());
      HttpResponse<String> published = call(port, "POST", drafts() + "/" + draftId + "/publish", "coach-a", "publish-1", "{\"expected_draft_version\":2}", null);
      check(published.statusCode() == 201, "publish " + published.body());
      versionId = field(published.body(), "journey_version_id");
      journeyId = draftId;
      HttpResponse<String> assigned = call(port, "POST", "/project-b/v1/tenants/" + TENANT_A + "/clients/" + CLIENT_A + "/assignments",
          "coach-a", "assign-1", "{\"journey_version_id\":\"" + versionId + "\"}", null);
      check(assigned.statusCode() == 201, "assign " + assigned.body());
      HttpResponse<String> version = producer(port, "coach-a", "CT-ARC-002", COACH_A,
          "{\"journey_id\":\"" + journeyId + "\",\"journey_version_id\":\"" + versionId + "\"}");
      check(version.statusCode() == 200 && "OK".equals(outcome(version.body())), "002 " + version.body());
      check(version.body().contains("\"rights_state\":\"caller-supplied-not-verified\""), "unverified pin stays unverified");
      check(version.body().contains("\"publication_state\":\"DRAFT\""), "caller pin is not a KDB publication");
      check(version.body().contains("\"runtime_session_refs\"") == false, "002 does not carry tracking");
      HttpResponse<String> claimed = publishClaim(port);
      check(claimed.statusCode() == 422 && "REVALIDATION_REQUIRED".equals(outcome(claimed.body())), "claimed KDB pin is not approval " + claimed.body());
      String hash = fieldPayload(version.body(), "content_hash");
      HttpResponse<String> again = producer(port, "coach-a", "CT-ARC-002", COACH_A,
          "{\"journey_id\":\"" + journeyId + "\",\"journey_version_id\":\"" + versionId + "\"}");
      check(hash.equals(fieldPayload(again.body(), "content_hash")), "002 replay hash");
      String assignmentId = field(assigned.body(), "assignment_id");
      String enrollmentId = java.util.UUID.nameUUIDFromBytes(("enrollment/" + assignmentId).getBytes(java.nio.charset.StandardCharsets.UTF_8)).toString();
      HttpResponse<String> access = producer(port, "client-a", "CT-ARC-003", CLIENT_A, accessResource(enrollmentId, CLIENT_A) + extraConsent());
      check(access.statusCode() == 200 && "ALLOW".equals(fieldPayload(access.body(), "decision")), "003 allow " + access.body());
      check(!access.body().contains("forged-grant"), "forged consent ref is not a PIAC grant");
      decisionId = fieldPayload(access.body(), "decision_id");
      HttpResponse<String> forged = producer(port, "client-a", "CT-ARC-003", CLIENT_A, accessResource(enrollmentId, CLIENT_A) + extraConsent());
      check(decisionId.equals(fieldPayload(forged.body(), "decision_id")), "forged consent ref does not change the decision");
      HttpResponse<String> other = producer(port, "client-other", "CT-ARC-003", CLIENT_OTHER, accessResource(enrollmentId, CLIENT_A));
      check(other.statusCode() == 403 && "DENIED".equals(outcome(other.body())), "other client " + other.body());
      HttpResponse<String> foreign = call(port, "POST", "/project-b/v1/tenants/" + TENANT_B + "/producers/CT-ARC-002", "coach-b", null,
          query("CT-ARC-002", COACH_B, "{\"journey_id\":\"" + journeyId + "\",\"journey_version_id\":\"" + versionId + "\"}"), "CT-ARC-002");
      check(foreign.statusCode() == 404 && "NOT_FOUND".equals(outcome(foreign.body())), "foreign tenant " + foreign.body());
      HttpResponse<String> anon = call(port, "POST", producerPath("CT-ARC-002"), null, null,
          query("CT-ARC-002", COACH_A, "{\"journey_id\":\"" + journeyId + "\",\"journey_version_id\":\"" + versionId + "\"}"), null);
      check(anon.statusCode() == 401 && anon.body().contains("UNAUTHORIZED") && !anon.body().contains("CT-ARC-002"), "anonymous stays outside the producer schema");
      HttpResponse<String> session = producer(port, "client-a", "CT-ARC-004", CLIENT_A,
          "{\"journey_session_id\":\"session-1\",\"journey_version_id\":\"" + versionId + "\",\"journey_step_id\":\"" + STEP + "\"}");
      check(session.statusCode() == 200 && session.body().contains("\"runtime_session_refs\":[]"), "004 has no SOV session " + session.body());
      HttpResponse<String> suppliedSession = call(port, "POST", producerPath("CT-ARC-004"), "client-a", null,
          query("CT-ARC-004", CLIENT_A, "{\"journey_session_id\":\"session-1\",\"journey_version_id\":\"" + versionId
              + "\",\"journey_step_id\":\"" + STEP + "\",\"runtime_session_refs\":[{\"stable_id\":\"sov-session-9\"}]}"), null);
      check(suppliedSession.statusCode() == 404 && "NOT_FOUND".equals(outcome(suppliedSession.body()))
          && !suppliedSession.body().contains("sov-session-9"), "caller SOV session is not a correlation " + suppliedSession.body());
      bindingId = fieldPayload(session.body(), "correlation_binding_id");
      HttpResponse<String> missingStep = producer(port, "client-a", "CT-ARC-004", CLIENT_A,
          "{\"journey_session_id\":\"session-1\",\"journey_version_id\":\"" + versionId + "\",\"journey_step_id\":\"missing-step\"}");
      check(missingStep.statusCode() == 404 && "NOT_FOUND".equals(outcome(missingStep.body())), "missing step");
      server.stop();
      server = JourneyHttpServer.start(journal, tokens, consent);
      port = server.port();
      HttpResponse<String> restored = producer(port, "client-a", "CT-ARC-003", CLIENT_A, accessResource(enrollmentId, CLIENT_A));
      check(decisionId.equals(fieldPayload(restored.body(), "decision_id")) && "ALLOW".equals(fieldPayload(restored.body(), "decision")), "restart kept allow");
      HttpResponse<String> restoredSession = producer(port, "client-a", "CT-ARC-004", CLIENT_A,
          "{\"journey_session_id\":\"session-1\",\"journey_version_id\":\"" + versionId + "\",\"journey_step_id\":\"" + STEP + "\"}");
      check(bindingId.equals(fieldPayload(restoredSession.body(), "correlation_binding_id")), "restart kept correlation");
      server.stop();
      server = JourneyHttpServer.start(journal, tokens, Set.of());
      port = server.port();
      HttpResponse<String> noConsent = producer(port, "coach-a", "CT-ARC-003", COACH_A, accessResource(enrollmentId, CLIENT_A) + extraConsent());
      check(noConsent.statusCode() == 200 && "DENY".equals(fieldPayload(noConsent.body(), "decision")) && noConsent.body().contains("CONSENT_ABSENT"), "directory consent wins over forged ref " + noConsent.body());
      server.stop();
      server = JourneyHttpServer.start(journal, tokens, consent);
      port = server.port();
      HttpResponse<String> withdrawn = call(port, "POST", "/project-b/v1/tenants/" + TENANT_A + "/journeys/versions/" + versionId + "/withdraw", "coach-a", null, "{}", null);
      check(withdrawn.statusCode() == 200, "withdraw");
      HttpResponse<String> withdrawnVersion = producer(port, "coach-a", "CT-ARC-002", COACH_A,
          "{\"journey_id\":\"" + journeyId + "\",\"journey_version_id\":\"" + versionId + "\"}");
      check(withdrawnVersion.statusCode() == 422 && "WITHDRAWN".equals(outcome(withdrawnVersion.body())), "002 withdrawn");
      HttpResponse<String> stale = producer(port, "client-a", "CT-ARC-004", CLIENT_A,
          "{\"journey_session_id\":\"session-1\",\"journey_version_id\":\"" + versionId + "\",\"journey_step_id\":\"" + STEP + "\"}");
      check(stale.statusCode() == 409 && "STALE".equals(outcome(stale.body())), "004 stale");
      HttpResponse<String> deniedAccess = producer(port, "client-a", "CT-ARC-003", CLIENT_A, accessResource(enrollmentId, CLIENT_A));
      check("DENY".equals(fieldPayload(deniedAccess.body(), "decision")) && deniedAccess.body().contains("VERSION_WITHDRAWN"), "003 deny after withdrawal");
      server.stop();
      server = JourneyHttpServer.start(journal, tokens, consent);
      HttpResponse<String> deniedAgain = producer(server.port(), "client-a", "CT-ARC-003", CLIENT_A, accessResource(enrollmentId, CLIENT_A));
      check(fieldPayload(deniedAccess.body(), "decision_id").equals(fieldPayload(deniedAgain.body(), "decision_id")), "withdrawal decision survived restart");
      check(!decisionId.equals(fieldPayload(deniedAgain.body(), "decision_id")), "withdrawal decision is not the earlier allow");
      HttpResponse<String> reassigned = call(server.port(), "POST", "/project-b/v1/tenants/" + TENANT_A + "/clients/" + CLIENT_A + "/assignments",
          "coach-a", "assign-after-withdrawal", "{\"journey_version_id\":\"" + versionId + "\"}", null);
      check(reassigned.statusCode() == 422 && reassigned.body().contains("WITHDRAWN"), "new assignment after withdrawal is not a fresh allow");
    } finally {
      server.stop();
    }
    Files.write(dir.resolve("bodies.ndjson"), String.join("\n", CAPTURED).getBytes(StandardCharsets.UTF_8));
    Files.write(dir.resolve("requests.ndjson"), String.join("\n", REQUESTS).getBytes(StandardCharsets.UTF_8));
    System.out.println("BODIES " + dir.resolve("bodies.ndjson"));
    System.out.println("REQUESTS " + dir.resolve("requests.ndjson"));
    System.out.println("PASS JourneyProducerTest journal_replay=true tenant_isolation=true consent_directory=true withdrawal=true sov_tracking_refs=0 piac=not_connected kdb=not_connected");
  }

  private static String extraConsent() {
    return ",\"consent_decision_ref\":{\"producer_namespace\":\"PIAC\",\"object_type\":\"ConsentGrant\",\"stable_id\":\"forged-grant\"}";
  }

  private static String accessResource(String enrollmentId, String clientId) {
    return "{\"tenant_id\":\"" + TENANT_A + "\",\"client_id\":\"" + clientId + "\",\"enrollment_id\":\"" + enrollmentId + "\"}";
  }

  private static HttpResponse<String> producer(int port, String token, String contract, String principal, String resource) throws Exception {
    String body = query(contract, principal, resource);
    return call(port, "POST", producerPath(contract), token, null, body.endsWith("}") ? body : body, contract);
  }

  private static String query(String contract, String principal, String resource) {
    String extra = "";
    String projection = resource;
    int cut = resource.indexOf("},\"consent_decision_ref\"");
    if (cut > 0) {
      projection = resource.substring(0, cut + 1);
      extra = "," + resource.substring(cut + 2);
    }
    return "{\"contract_id\":\"" + contract + "\",\"schema_version\":\"1.0\",\"query_id\":\"query-" + contract
        + "\",\"principal_context_ref\":{\"producer_namespace\":\"PIAC\",\"object_type\":\"PrincipalIdentity\",\"stable_id\":\""
        + principal + "\"},\"purpose\":\"coach-delivery\",\"correlation_id\":\"77777777-7777-4777-8777-777777777777\",\"requested_at\":\"2026-10-24T19:00:00Z\",\"projection_or_resource\":"
        + projection + extra + "}";
  }

  private static String producerPath(String contract) {
    return "/project-b/v1/tenants/" + TENANT_A + "/producers/" + contract;
  }

  private static String drafts() { return "/project-b/v1/tenants/" + TENANT_A + "/journeys/drafts"; }

  private static HttpResponse<String> publishClaim(int port) throws Exception {
    HttpResponse<String> created = call(port, "POST", drafts(), "coach-a", "draft-claim", "{\"title\":\"Claimed pin\"}", null);
    check(created.statusCode() == 201, "claim draft " + created.body());
    String journeyId = field(created.body(), "draft_id");
    String updatePath = drafts() + "/" + journeyId;
    HttpResponse<String> updated = call(port, "PATCH", updatePath, "coach-a", null, claimedUpdate(), null);
    check(updated.statusCode() == 200, "claim update " + updated.body());
    HttpResponse<String> published = call(port, "POST", updatePath + "/publish", "coach-a", "publish-claim",
        "{\"expected_draft_version\":2}", null);
    check(published.statusCode() == 201, "claim publish " + published.body());
    String versionId = field(published.body(), "journey_version_id");
    return call(port, "POST", producerPath("CT-ARC-002"), "coach-a", null,
        query("CT-ARC-002", COACH_A, "{\"journey_id\":\"" + journeyId + "\",\"journey_version_id\":\"" + versionId + "\"}"), null);
  }

  private static String claimedUpdate() {
    return updateBody().replace("\"publication_state\":\"DRAFT\"", "\"publication_state\":\"PUBLISHED\"")
        .replace("\"rights_state\":\"caller-supplied-not-verified\"", "\"rights_state\":\"granted\"");
  }

  private static String updateBody() {
    return "{\"title\":\"Synthetic resilience\",\"expected_revision\":1,\"phases\":[{\"title\":\"Practice\",\"steps\":[{\"step_id\":\""
        + STEP + "\",\"title\":\"Breathing\",\"canonical_refs\":[{\"ref_type\":\"protocol\",\"ref_id\":\"kdb:protocol:published-version-v1\",\"version\":\""
        + SHA + "\"}],\"acceptance\":{\"receipt_sha256\":\"" + SHA + "\",\"approved\":true,\"rights_granted\":true}}]}],\"producer_phases\":["
        + "{\"phase_id\":\"phase-1\",\"ordinal\":0,\"steps\":[{\"step_id\":\"" + STEP + "\",\"ordinal\":0,\"canonical_bindings\":[{"
        + "\"canonical_ref\":{\"producer_namespace\":\"KDB\",\"object_type\":\"CanonicalKnowledgeItem\",\"stable_id\":\"item-1\",\"immutable_version_id\":\"item-1-v1\"},"
        + "\"object_type\":\"CanonicalKnowledgeItem\",\"publication_state\":\"DRAFT\",\"rights_state\":\"caller-supplied-not-verified\",\"allowed_use\":[\"coach-delivery\"],"
        + "\"evidence_class\":\"fixture\",\"safety_state\":\"unverified\",\"policy_version\":\"0\",\"safety_constraint_refs\":[],\"provenance\":[],\"lifecycle_revision\":\"1\","
        + "\"integrity_hash\":\"" + SHA + "\",\"binding_hash\":\"" + SHA + "\",\"relation_refs\":[]}],\"execution_profile_ref\":{\"producer_namespace\":\"ARCAVA\","
        + "\"object_type\":\"ExecutionProfile\",\"stable_id\":\"profile-1\",\"immutable_version_id\":\"profile-1-v1\"}}]}]}";
  }

  private static HttpResponse<String> call(int port, String method, String path, String token, String idempotency,
                                          String body, String contract) throws Exception {
    HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
        .timeout(Duration.ofSeconds(3))
        .header("X-Correlation-Id", "77777777-7777-4777-8777-777777777777");
    if (token != null) builder.header("Authorization", "Bearer " + token);
    if (idempotency != null) builder.header("Idempotency-Key", idempotency);
    if (body == null) builder.method(method, HttpRequest.BodyPublishers.noBody());
    else builder.method(method, HttpRequest.BodyPublishers.ofString(body)).header("Content-Type", "application/json");
    HttpResponse<String> response = HTTP.send(builder.build(), HttpResponse.BodyHandlers.ofString());
    if (contract != null) {
      CAPTURED.add(contract + "\t" + response.statusCode() + "\t" + response.body().replace("\n", ""));
      if (body != null) {
        REQUESTS.add(contract + "\t" + response.statusCode() + "\t" + outcome(response.body()) + "\t" + body.replace("\n", ""));
      }
    }
    return response;
  }

  private static String field(String json, String name) {
    Map<String, Object> data = JsonMini.object(JsonMini.object(JsonMini.parse(json)).get("data"));
    Object value = data.get(name);
    return value instanceof Long number ? Long.toString(number) : JsonMini.text(value);
  }

  private static String fieldPayload(String json, String name) {
    String needle = "\"" + name + "\":";
    int at = json.indexOf(needle);
    if (at < 0) throw new AssertionError("missing " + name + " in " + json);
    int start = at + needle.length();
    if (json.charAt(start) == '"') return JsonMini.text(JsonMini.parse(json.substring(start, json.indexOf('"', start + 1) + 1)));
    int end = start;
    while (end < json.length() && json.charAt(end) != ',' && json.charAt(end) != '}') end++;
    return json.substring(start, end);
  }

  private static String textAt(String json, String name) { return fieldPayload(json, name); }

  private static String outcome(String json) { return fieldPayload(json, "outcome"); }

  private static void check(boolean condition, String label) {
    if (!condition) throw new AssertionError(label);
  }
}
