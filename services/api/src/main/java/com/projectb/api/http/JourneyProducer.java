package com.projectb.api.http;

import java.time.Instant;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import com.projectb.api.domain.JourneyJournal;
import com.projectb.api.domain.JourneyJournal.EnrollmentLink;
import com.projectb.api.domain.JourneyJournal.Projection;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.json.JsonMini;

/**
 * Journal-backed CT-ARC-002, CT-ARC-003 and CT-ARC-004 reads.
 * Bearer identity is a local directory. principal_context_ref and consent_decision_ref
 * are not treated as PIAC decisions. Canonical bindings are stored caller input.
 * runtime_session_refs stay empty: this service does not own SOV tracking.
 */
public final class JourneyProducer {
  private JourneyProducer() {}

  public record Reply(int status, String body) {}

  public static Reply handle(String contract, Actor actor, Set<String> consent, JourneyJournal journal,
                             Map<String, Object> body) {
    if (!Set.of("CT-ARC-002", "CT-ARC-003", "CT-ARC-004").contains(contract))
      throw new IllegalArgumentException("unknown producer");
    if (!contract.equals(body.get("contract_id")) || !"1.0".equals(body.get("schema_version")))
      throw new IllegalArgumentException("contract mismatch");
    String correlation = JsonMini.text(body.get("correlation_id"));
    String requestId = JsonMini.text(body.get("query_id"));
    Map<String, Object> principal = JsonMini.object(body.get("principal_context_ref"));
    boolean principalMatches = actor.subjectId().equals(principal.get("stable_id"));
    Map<String, Object> resource = JsonMini.object(body.get("projection_or_resource"));
    String asOf = Instant.now().toString();
    return switch (contract) {
      case "CT-ARC-002" -> version(actor, journal, resource, principalMatches, correlation, requestId, asOf);
      case "CT-ARC-003" -> access(actor, consent, journal, resource, principalMatches, body, correlation, requestId, asOf);
      case "CT-ARC-004" -> correlation(actor, journal, resource, principalMatches, correlation, requestId, asOf);
      default -> throw new IllegalArgumentException("unknown producer");
    };
  }

  private static Reply version(Actor actor, JourneyJournal journal, Map<String, Object> resource,
                               boolean principalMatches, String correlation, String requestId, String asOf) {
    if (!principalMatches) return error("CT-ARC-002", "NOT_FOUND", "TERMINAL", "PRINCIPAL_MISMATCH", correlation, requestId, asOf, 404);
    Projection projection = find(journal, actor, text(resource, "journey_version_id"));
    if (projection == null || !projection.journeyId().equals(text(resource, "journey_id")))
      return error("CT-ARC-002", "NOT_FOUND", "TERMINAL", "VERSION_ABSENT", correlation, requestId, asOf, 404);
    if ("WITHDRAWN".equals(projection.publicationState()))
      return error("CT-ARC-002", "WITHDRAWN", "TERMINAL", "VERSION_WITHDRAWN", correlation, requestId, asOf, 422);
    if (!projection.phasesJson().contains("\"canonical_bindings\"") || TrustedKdbVerifier.NONE.claimsApproval(projection.phasesJson()))
      return error("CT-ARC-002", "REVALIDATION_REQUIRED", "AFTER_STATE_CHANGE", "CANONICAL_PIN_UNVERIFIED", correlation, requestId, asOf, 422);
    String payload = "{\"journey_id\":" + JsonMini.quote(projection.journeyId())
        + ",\"journey_version_id\":" + JsonMini.quote(projection.versionId())
        + ",\"publication_state\":\"PUBLISHED\",\"published_at\":" + JsonMini.quote(projection.publishedAt())
        + ",\"content_hash\":" + JsonMini.quote(projection.contentHash())
        + ",\"phases\":" + projection.phasesJson()
        + ",\"review_ref\":{\"producer_namespace\":\"ARCAVA\",\"object_type\":\"ProducerAuditRecord\",\"stable_id\":"
        + JsonMini.quote("review-" + projection.versionId()) + "}}";
    return new Reply(200, ok("CT-ARC-002", correlation, requestId, asOf, payload));
  }

  private static Reply access(Actor actor, Set<String> consent, JourneyJournal journal, Map<String, Object> resource,
                              boolean principalMatches, Map<String, Object> body, String correlation, String requestId, String asOf) {
    if (!principalMatches || !actor.tenantId().equals(text(resource, "tenant_id")))
      return error("CT-ARC-003", "DENIED", "TERMINAL", "PRINCIPAL_MISMATCH", correlation, requestId, asOf, 403);
    EnrollmentLink link = journal.enrollment(UUID.fromString(text(resource, "enrollment_id")));
    if (link == null || !link.tenantId().equals(actor.tenantId()) || !link.clientId().equals(text(resource, "client_id")))
      return error("CT-ARC-003", "DENIED", "TERMINAL", "ENROLLMENT_MISMATCH", correlation, requestId, asOf, 403);
    if (actor.role() == Role.CLIENT && !actor.subjectId().equals(link.clientId()))
      return error("CT-ARC-003", "DENIED", "TERMINAL", "CLIENT_MISMATCH", correlation, requestId, asOf, 403);
    Projection projection = find(journal, actor, link.versionId());
    boolean withdrawn = projection == null || "WITHDRAWN".equals(projection.publicationState());
    boolean consented = consent.contains(link.tenantId() + "|" + link.clientId());
    String decision = !withdrawn && consented ? "ALLOW" : "DENY";
    String reason = withdrawn ? "VERSION_WITHDRAWN" : consented ? "LOCAL_DIRECTORY_MATCH" : "CONSENT_ABSENT";
    String decisionId = UUID.nameUUIDFromBytes((link.enrollmentId() + "|" + decision + "|" + reason)
        .getBytes(java.nio.charset.StandardCharsets.UTF_8)).toString();
    String state = withdrawn ? "REVOKED" : "ACTIVE";
    String revocation = withdrawn ? "REVOKED" : "ACTIVE";
    String from = projection == null ? asOf : projection.publishedAt();
    String payload = "{\"enrollment_ref\":{\"producer_namespace\":\"ARCAVA\",\"object_type\":\"Enrollment\",\"stable_id\":"
        + JsonMini.quote(link.enrollmentId()) + "},\"enrollment_revision\":" + JsonMini.quote(withdrawn ? "2" : "1")
        + ",\"enrollment_state\":" + JsonMini.quote(state)
        + ",\"assignment_refs\":[{\"producer_namespace\":\"ARCAVA\",\"object_type\":\"CoachAssignment\",\"stable_id\":"
        + JsonMini.quote(link.assignmentId()) + "}],\"effective_access\":{\"decision_id\":" + JsonMini.quote(decisionId)
        + ",\"principal_id\":" + JsonMini.quote(actor.subjectId())
        + ",\"scope\":{\"kind\":\"TENANT\",\"tenant_id\":" + JsonMini.quote(link.tenantId())
        + ",\"client_id\":" + JsonMini.quote(link.clientId()) + "},\"purpose\":" + JsonMini.quote(JsonMini.text(body.get("purpose")))
        + ",\"policy_version\":\"local-directory-not-piac\",\"decision\":" + JsonMini.quote(decision)
        + ",\"reason_codes\":[" + JsonMini.quote(reason) + "],\"validity\":{\"valid_from\":" + JsonMini.quote(from)
        + ",\"valid_until\":null,\"revocation_state\":" + JsonMini.quote(revocation)
        + "},\"evidence_ref\":{\"producer_namespace\":\"ARCAVA\",\"object_type\":\"ProducerAuditRecord\",\"stable_id\":"
        + JsonMini.quote("access-" + decisionId) + "}}}";
    return new Reply(200, ok("CT-ARC-003", correlation, requestId, asOf, payload));
  }

  private static Reply correlation(Actor actor, JourneyJournal journal, Map<String, Object> resource,
                                   boolean principalMatches, String correlation, String requestId, String asOf) {
    if (!principalMatches) return error("CT-ARC-004", "NOT_FOUND", "TERMINAL", "PRINCIPAL_MISMATCH", correlation, requestId, asOf, 404);
    Projection projection = find(journal, actor, text(resource, "journey_version_id"));
    if (projection == null) return error("CT-ARC-004", "NOT_FOUND", "TERMINAL", "VERSION_ABSENT", correlation, requestId, asOf, 404);
    if ("WITHDRAWN".equals(projection.publicationState()))
      return error("CT-ARC-004", "STALE", "RECONCILE", "VERSION_WITHDRAWN", correlation, requestId, asOf, 409);
    String stepId = text(resource, "journey_step_id");
    if (resource.containsKey("runtime_session_refs"))
      return error("CT-ARC-004", "NOT_FOUND", "TERMINAL", "SOV_SESSION_NOT_OWNED", correlation, requestId, asOf, 404);
    if (!journal.stepPresent(projection, stepId))
      return error("CT-ARC-004", "NOT_FOUND", "TERMINAL", "STEP_ABSENT", correlation, requestId, asOf, 404);
    String sessionId = text(resource, "journey_session_id");
    String bindingId = UUID.nameUUIDFromBytes((projection.versionId() + "|" + stepId + "|" + sessionId)
        .getBytes(java.nio.charset.StandardCharsets.UTF_8)).toString();
    String payload = "{\"correlation_binding_id\":" + JsonMini.quote(bindingId)
        + ",\"journey_session_id\":" + JsonMini.quote(sessionId)
        + ",\"journey_version_id\":" + JsonMini.quote(projection.versionId())
        + ",\"journey_step_id\":" + JsonMini.quote(stepId)
        + ",\"runtime_session_refs\":[],\"source_ref\":{\"schema_version\":1,\"variant\":\"ARCAVA_DELIVERY_BINDING\",\"journey_version_id\":"
        + JsonMini.quote(projection.versionId()) + ",\"journey_step_id\":" + JsonMini.quote(stepId) + "}}";
    return new Reply(200, ok("CT-ARC-004", correlation, requestId, asOf, payload));
  }

  private static Projection find(JourneyJournal journal, Actor actor, String versionId) {
    Projection projection = journal.projection(UUID.fromString(versionId));
    if (projection == null || !projection.tenantId().equals(actor.tenantId())) return null;
    return projection;
  }

  private static String text(Map<String, Object> body, String key) { return JsonMini.text(body.get(key)); }

  private static String ok(String contract, String correlation, String requestId, String asOf, String payload) {
    return "{\"contract_id\":" + JsonMini.quote(contract) + ",\"schema_version\":\"1.0\",\"correlation_id\":"
        + JsonMini.quote(correlation) + ",\"request_id\":" + JsonMini.quote(requestId)
        + ",\"outcome\":\"OK\",\"as_of\":" + JsonMini.quote(asOf) + ",\"payload\":" + payload + "}";
  }

  private static Reply error(String contract, String outcome, String retry, String reason,
                             String correlation, String requestId, String asOf, int status) {
    String body = "{\"contract_id\":" + JsonMini.quote(contract) + ",\"schema_version\":\"1.0\",\"correlation_id\":"
        + JsonMini.quote(correlation) + ",\"request_id\":" + JsonMini.quote(requestId)
        + ",\"outcome\":" + JsonMini.quote(outcome) + ",\"as_of\":" + JsonMini.quote(asOf)
        + ",\"error\":{\"code\":" + JsonMini.quote(outcome) + ",\"reason_codes\":[" + JsonMini.quote(reason)
        + "],\"retry_disposition\":" + JsonMini.quote(retry) + "}}";
    return new Reply(status, body);
  }
}
