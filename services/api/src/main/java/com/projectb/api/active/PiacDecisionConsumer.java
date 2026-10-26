package com.projectb.api.active;

/**
 * Arcava-side consumer of a PIAC decision.
 * SOV owns the identity and consent authority. This port does not invent one.
 */
public interface PiacDecisionConsumer {
  boolean admitsLiveTransport();

  PiacDecision decide(PiacQuery query);

  record PiacQuery(String bearer, String tenantId, String purpose, String correlationId,
                   boolean timedOut, boolean stale, boolean transportError, boolean consentRevoked) {}

  record PiacDecision(boolean allowed, String subjectId, String tenantId, String reason) {}
}
