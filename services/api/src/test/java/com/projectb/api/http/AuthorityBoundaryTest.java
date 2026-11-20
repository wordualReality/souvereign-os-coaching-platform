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

/** ARC-02: loopback fixtures are not a live PIAC or KDB authority. */
public final class AuthorityBoundaryTest {
  private static final String TENANT = "11111111-1111-4111-8111-111111111111";
  private static final String COACH = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  private static final String CLIENT = "33333333-3333-4333-8333-333333333333";
  private static final String STEP = "66666666-6666-4666-8666-666666666666";
  private static final String SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

  public static void main(String[] args) throws Exception {
    liveProfileRefusesFixtureAuthorities();
    loopbackProfileAndNegativeAuthority();
    System.out.println("PASS AuthorityBoundaryTest live_profile=closed fixture_bearer=loopback_only consent_body=ignored kdb_claim=unverified sov_session=rejected");
  }

  private static void liveProfileRefusesFixtureAuthorities() throws Exception {
    Path journal = Files.createTempDirectory("arcava-live").resolve("journal.ndjson");
    expectClosed(() -> JourneyHttpServer.startLive(journal, TrustedPiacVerifier.NONE, TrustedKdbVerifier.NONE));
    expectClosed(() -> JourneyHttpServer.startLive(journal, null, null));
    check(!TrustedPiacVerifier.NONE.verifiesLiveIdentity(), "fixture PIAC verifier");
    check(!TrustedKdbVerifier.NONE.verifiesLivePublication(), "NONE is not a KDB verifier");
    check(TrustedKdbVerifier.NONE.claimsApproval("[{\"canonical_ref\":{\"stable_id\":\"item-1\"},\"publication_state\":\"PUBLISHED\",\"rights_state\":\"caller-supplied-not-verified\"}]"), "caller claim is detected");
    check(!Files.exists(journal), "closed live start does not create a service journal");
  }

  private static void loopbackProfileAndNegativeAuthority() throws Exception {
    Path journal = Files.createTempDirectory("arcava-boundary").resolve("journal.ndjson");
    Map<String, Actor> tokens = Map.of(
        "coach-a", new Actor(TENANT, COACH, Role.COACH),
        "client-a", new Actor(TENANT, CLIENT, Role.CLIENT));
    JourneyHttpServer server = JourneyHttpServer.start(journal, tokens, Set.of(TENANT + "|" + CLIENT));
    try {
      HttpResponse<String> health = call(server.port(), "GET", "/project-b/v1/health", null, null, null);
      check(health.statusCode() == 200 && health.body().contains("\"profile\":\"TEST_LOOPBACK_ONLY\"")
          && health.body().contains("\"runtime\":\"loopback_fixture\"")
          && health.body().contains("\"piac\":\"not_connected\"")
          && health.body().contains("\"kdb\":\"not_connected\""), "health " + health.body());
      HttpResponse<String> anonymous = call(server.port(), "POST", drafts(), null, "create-anon", "{\"title\":\"Synthetic resilience\"}");
      check(anonymous.statusCode() == 401, "missing bearer");
      HttpResponse<String> unknown = call(server.port(), "POST", drafts(), "not-a-piac-token", "create-unknown", "{\"title\":\"Synthetic resilience\"}");
      check(unknown.statusCode() == 401, "untrusted bearer");
      String draftId = field(call(server.port(), "POST", drafts(), "coach-a", "create-1", "{\"title\":\"Synthetic resilience\"}").body(), "draft_id");
      check(call(server.port(), "PATCH", drafts() + "/" + draftId, "coach-a", null, updateBody("DRAFT", "caller-supplied-not-verified")).statusCode() == 200, "update");
      HttpResponse<String> published = call(server.port(), "POST", drafts() + "/" + draftId + "/publish", "coach-a", "publish-1", "{\"expected_draft_version\":2}");
      check(published.statusCode() == 201, "publish " + published.body());
      String versionId = field(published.body(), "journey_version_id");
      JourneyHttpServer denied = JourneyHttpServer.start(journal, tokens, Set.of());
      try {
        HttpResponse<String> bodyConsent = call(denied.port(), "POST", "/project-b/v1/tenants/" + TENANT + "/clients/" + CLIENT + "/assignments",
            "coach-a", "assign-body", "{\"journey_version_id\":\"" + versionId + "\",\"consent_verified\":true}");
        check(bodyConsent.statusCode() == 422 && bodyConsent.body().contains("CONSENT_REQUIRED"), "body consent " + bodyConsent.body());
      } finally {
        denied.stop();
      }
      HttpResponse<String> assigned = call(server.port(), "POST", "/project-b/v1/tenants/" + TENANT + "/clients/" + CLIENT + "/assignments",
          "coach-a", "assign-1", "{\"journey_version_id\":\"" + versionId + "\",\"consent_verified\":false}");
      check(assigned.statusCode() == 201, "directory consent " + assigned.body());
      String enrollmentId = java.util.UUID.nameUUIDFromBytes(("enrollment/" + field(assigned.body(), "assignment_id")).getBytes(java.nio.charset.StandardCharsets.UTF_8)).toString();
      HttpResponse<String> forged = producer(server.port(), "client-a", "CT-ARC-003", CLIENT,
          "{\"tenant_id\":\"" + TENANT + "\",\"client_id\":\"" + CLIENT + "\",\"enrollment_id\":\"" + enrollmentId + "\"}", true);
      check(forged.statusCode() == 200 && forged.body().contains("\"decision\":\"ALLOW\"") && !forged.body().contains("forged-grant"), "forged consent ref " + forged.body());
      HttpResponse<String> claimed = call(server.port(), "POST", drafts(), "coach-a", "draft-claim", "{\"title\":\"Claimed pin\"}");
      String claimedId = field(claimed.body(), "draft_id");
      check(call(server.port(), "PATCH", drafts() + "/" + claimedId, "coach-a", null, updateBody("PUBLISHED", "granted")).statusCode() == 200, "claimed update");
      HttpResponse<String> claimedPublish = call(server.port(), "POST", drafts() + "/" + claimedId + "/publish", "coach-a", "publish-claim", "{\"expected_draft_version\":2}");
      HttpResponse<String> revalidation = producer(server.port(), "coach-a", "CT-ARC-002", COACH,
          "{\"journey_id\":\"" + claimedId + "\",\"journey_version_id\":\"" + field(claimedPublish.body(), "journey_version_id") + "\"}", false);
      check(revalidation.statusCode() == 422 && revalidation.body().contains("REVALIDATION_REQUIRED"), "kdb claim " + revalidation.body());
      HttpResponse<String> session = producer(server.port(), "client-a", "CT-ARC-004", CLIENT,
          "{\"journey_session_id\":\"session-1\",\"journey_version_id\":\"" + versionId + "\",\"journey_step_id\":\"" + STEP
              + "\",\"runtime_session_refs\":[{\"stable_id\":\"sov-session-9\"}]}", false);
      check(session.statusCode() == 404 && session.body().contains("NOT_FOUND") && !session.body().contains("sov-session-9"), "sov session " + session.body());
    } finally {
      server.stop();
    }
  }

  private static void expectClosed(Attempt attempt) {
    try {
      attempt.run();
      throw new AssertionError("live runtime started");
    } catch (IllegalStateException ex) {
      check(ex.getMessage().contains("live runtime closed"), ex.getMessage());
    } catch (RuntimeException ex) {
      throw ex;
    }
  }

  private interface Attempt { void run(); }

  private static HttpResponse<String> producer(int port, String token, String contract, String principal, String resource, boolean forged) throws Exception {
    String extra = forged ? ",\"consent_decision_ref\":{\"producer_namespace\":\"PIAC\",\"object_type\":\"ConsentGrant\",\"stable_id\":\"forged-grant\"}" : "";
    String body = "{\"contract_id\":\"" + contract + "\",\"schema_version\":\"1.0\",\"query_id\":\"query-" + contract
        + "\",\"principal_context_ref\":{\"producer_namespace\":\"PIAC\",\"object_type\":\"PrincipalIdentity\",\"stable_id\":\""
        + principal + "\"},\"purpose\":\"coach-delivery\",\"correlation_id\":\"77777777-7777-4777-8777-777777777777\",\"requested_at\":\"2026-10-25T09:00:00Z\",\"projection_or_resource\":"
        + resource + extra + "}";
    return call(port, "POST", "/project-b/v1/tenants/" + TENANT + "/producers/" + contract, token, null, body);
  }

  private static String drafts() { return "/project-b/v1/tenants/" + TENANT + "/journeys/drafts"; }

  private static String updateBody(String publicationState, String rightsState) {
    return "{\"title\":\"Synthetic resilience\",\"expected_revision\":1,\"phases\":[{\"title\":\"Practice\",\"steps\":[{\"step_id\":\""
        + STEP + "\",\"title\":\"Breathing\",\"canonical_refs\":[{\"ref_type\":\"protocol\",\"ref_id\":\"kdb:protocol:published-version-v1\",\"version\":\""
        + SHA + "\"}],\"acceptance\":{\"receipt_sha256\":\"" + SHA + "\",\"approved\":true,\"rights_granted\":true}}]}],\"producer_phases\":["
        + "{\"phase_id\":\"phase-1\",\"ordinal\":0,\"steps\":[{\"step_id\":\"" + STEP + "\",\"ordinal\":0,\"canonical_bindings\":[{"
        + "\"canonical_ref\":{\"producer_namespace\":\"KDB\",\"object_type\":\"CanonicalKnowledgeItem\",\"stable_id\":\"item-1\",\"immutable_version_id\":\"item-1-v1\"},"
        + "\"object_type\":\"CanonicalKnowledgeItem\",\"publication_state\":\"" + publicationState + "\",\"rights_state\":\"" + rightsState + "\",\"allowed_use\":[\"coach-delivery\"],"
        + "\"evidence_class\":\"fixture\",\"safety_state\":\"unverified\",\"policy_version\":\"0\",\"safety_constraint_refs\":[],\"provenance\":[],\"lifecycle_revision\":\"1\","
        + "\"integrity_hash\":\"" + SHA + "\",\"binding_hash\":\"" + SHA + "\",\"relation_refs\":[]}],\"execution_profile_ref\":{\"producer_namespace\":\"ARCAVA\","
        + "\"object_type\":\"ExecutionProfile\",\"stable_id\":\"profile-1\",\"immutable_version_id\":\"profile-1-v1\"}}]}]}";
  }

  private static HttpResponse<String> call(int port, String method, String path, String token, String idempotency, String body) throws Exception {
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
    Object value = JsonMini.object(JsonMini.object(JsonMini.parse(json)).get("data")).get(name);
    return JsonMini.text(value);
  }

  private static void check(boolean condition, String label) {
    if (!condition) throw new AssertionError(label);
  }
}
