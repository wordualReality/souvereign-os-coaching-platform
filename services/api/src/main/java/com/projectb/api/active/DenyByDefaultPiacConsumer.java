package com.projectb.api.active;

/** No PIAC transport is connected. Every query is denied. */
public final class DenyByDefaultPiacConsumer implements PiacDecisionConsumer {
  @Override
  public boolean admitsLiveTransport() { return false; }

  @Override
  public PiacDecision decide(PiacQuery query) {
    if (query == null) return deny("PIAC_QUERY_ABSENT");
    if (query.bearer() == null || query.bearer().isBlank()) return deny("BEARER_ABSENT");
    if (query.timedOut()) return deny("PIAC_TIMEOUT");
    if (query.stale()) return deny("PIAC_STALE");
    if (query.transportError()) return deny("PIAC_ERROR");
    if (query.consentRevoked()) return deny("CONSENT_REVOKED");
    return deny("PIAC_NOT_CONNECTED");
  }

  private static PiacDecision deny(String reason) {
    return new PiacDecision(false, null, null, reason);
  }
}
