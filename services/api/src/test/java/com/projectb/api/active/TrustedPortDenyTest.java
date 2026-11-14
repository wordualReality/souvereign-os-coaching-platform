package com.projectb.api.active;

import com.projectb.api.active.KdbPublicationVerifier.KdbPinQuery;
import com.projectb.api.active.KdbPublicationVerifier.KdbVerdict;
import com.projectb.api.active.PiacDecisionConsumer.PiacDecision;
import com.projectb.api.active.PiacDecisionConsumer.PiacQuery;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class TrustedPortDenyTest {
  private final PiacDecisionConsumer piac = new DenyByDefaultPiacConsumer();
  private final KdbPublicationVerifier kdb = new DenyByDefaultKdbPublicationVerifier();
  private final LiveAccessGate gate = new LiveAccessGate();

  @Test
  void missingAndFailedPiacQueriesStayDenied() {
    assertThat(piac.decide(null).reason()).isEqualTo("PIAC_QUERY_ABSENT");
    assertThat(piac.decide(query("", false, false, false, false)).reason()).isEqualTo("BEARER_ABSENT");
    assertThat(piac.decide(query("coach-a", true, false, false, false)).reason()).isEqualTo("PIAC_TIMEOUT");
    assertThat(piac.decide(query("coach-a", false, true, false, false)).reason()).isEqualTo("PIAC_STALE");
    assertThat(piac.decide(query("coach-a", false, false, true, false)).reason()).isEqualTo("PIAC_ERROR");
    assertThat(piac.decide(query("coach-a", false, false, false, true)).reason()).isEqualTo("CONSENT_REVOKED");
    PiacDecision fixture = piac.decide(query("coach-a", false, false, false, false));
    assertThat(fixture.allowed()).isFalse();
    assertThat(fixture.reason()).isEqualTo("PIAC_NOT_CONNECTED");
  }

  @Test
  void callerSuppliedPublicationDoesNotVerify() {
    assertThat(kdb.verify(null).reason()).isEqualTo("KDB_QUERY_ABSENT");
    assertThat(kdb.verify(pin(true, false, false)).reason()).isEqualTo("KDB_TIMEOUT");
    assertThat(kdb.verify(pin(false, true, false)).reason()).isEqualTo("KDB_STALE");
    assertThat(kdb.verify(pin(false, false, true)).reason()).isEqualTo("KDB_ERROR");
    KdbVerdict claimed = kdb.verify(new KdbPinQuery("kdb:claimed", "PUBLISHED", "granted", false, false, false));
    assertThat(claimed.published()).isFalse();
    assertThat(claimed.reason()).isEqualTo("KDB_NOT_CONNECTED");
  }

  @Test
  void positiveDummyVerdictStillCannotAdmitProtectedTraffic() {
    PiacDecisionConsumer allow = new PiacDecisionConsumer() {
      public boolean admitsLiveTransport() { return true; }
      public PiacDecision decide(PiacQuery query) {
        return new PiacDecision(true, "subject", "tenant", "ALLOW");
      }
    };
    KdbPublicationVerifier allowPin = new KdbPublicationVerifier() {
      public boolean admitsLiveTransport() { return true; }
      public KdbVerdict verify(KdbPinQuery query) { return new KdbVerdict(true, "PUBLISHED"); }
    };
    assertThat(gate.protectedTrafficReady(allow, allowPin)).isTrue();
    assertThat(gate.denial(allow, allowPin, query("coach-a", false, false, false, false), pin(false, false, false)))
        .isEqualTo("LIVE_ADAPTER_NOT_ADMITTED");
    assertThat(gate.denial(piac, kdb, query("coach-a", false, false, false, false), pin(false, false, false)))
        .isEqualTo("LIVE_AUTHORITY_CLOSED");
  }

  private static PiacQuery query(String bearer, boolean timedOut, boolean stale, boolean error, boolean revoked) {
    return new PiacQuery(bearer, "11111111-1111-4111-8111-111111111111", "coach-delivery",
        "22222222-2222-4222-8222-222222222222", timedOut, stale, error, revoked);
  }

  private static KdbPinQuery pin(boolean timedOut, boolean stale, boolean error) {
    return new KdbPinQuery("kdb:protocol:published-version-v1", "PUBLISHED", "granted", timedOut, stale, error);
  }
}
