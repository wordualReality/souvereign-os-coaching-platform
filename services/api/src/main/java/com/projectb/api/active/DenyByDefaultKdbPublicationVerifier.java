package com.projectb.api.active;

/** No KDB publication transport is connected. Every pin is unverified. */
public final class DenyByDefaultKdbPublicationVerifier implements KdbPublicationVerifier {
  @Override
  public boolean admitsLiveTransport() { return false; }

  @Override
  public KdbVerdict verify(KdbPinQuery query) {
    if (query == null) return deny("KDB_QUERY_ABSENT");
    if (query.timedOut()) return deny("KDB_TIMEOUT");
    if (query.stale()) return deny("KDB_STALE");
    if (query.transportError()) return deny("KDB_ERROR");
    return deny("KDB_NOT_CONNECTED");
  }

  private static KdbVerdict deny(String reason) {
    return new KdbVerdict(false, reason);
  }
}
