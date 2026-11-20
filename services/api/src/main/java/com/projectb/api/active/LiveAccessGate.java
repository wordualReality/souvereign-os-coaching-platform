package com.projectb.api.active;

import com.projectb.api.active.KdbPublicationVerifier.KdbPinQuery;
import com.projectb.api.active.KdbPublicationVerifier.KdbVerdict;
import com.projectb.api.active.PiacDecisionConsumer.PiacDecision;
import com.projectb.api.active.PiacDecisionConsumer.PiacQuery;

/**
 * Protected traffic stays closed in this package.
 * A positive fixture or dummy verdict is not a live admission.
 */
public final class LiveAccessGate {
  public boolean protectedTrafficReady(PiacDecisionConsumer piac, KdbPublicationVerifier kdb) {
    return piac != null && kdb != null && piac.admitsLiveTransport() && kdb.admitsLiveTransport();
  }

  public String denial(PiacDecisionConsumer piac, KdbPublicationVerifier kdb, PiacQuery query, KdbPinQuery pin) {
    if (!protectedTrafficReady(piac, kdb)) return "LIVE_AUTHORITY_CLOSED";
    PiacDecision decision = piac.decide(query);
    if (decision == null || !decision.allowed() || decision.subjectId() == null || decision.tenantId() == null)
      return decision == null ? "PIAC_ERROR" : decision.reason();
    KdbVerdict verdict = kdb.verify(pin);
    if (verdict == null || !verdict.published()) return verdict == null ? "KDB_ERROR" : verdict.reason();
    return "LIVE_ADAPTER_NOT_ADMITTED";
  }
}
