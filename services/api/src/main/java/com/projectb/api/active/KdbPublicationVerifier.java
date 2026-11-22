package com.projectb.api.active;

/**
 * Arcava-side consumer of a KDB publication and rights verdict.
 * KDB owns that authority. A caller-supplied pin is not a verdict.
 */
public interface KdbPublicationVerifier {
  boolean admitsLiveTransport();

  KdbVerdict verify(KdbPinQuery query);

  record KdbPinQuery(String stableId, String publicationState, String rightsState,
                     boolean timedOut, boolean stale, boolean transportError) {}

  record KdbVerdict(boolean published, String reason) {}
}
