package com.projectb.api.http;

/**
 * No live PIAC verifier is connected.
 * A bearer map in the loopback profile is a fixture, not a verified identity.
 */
public final class TrustedPiacVerifier {
  public static final TrustedPiacVerifier NONE = new TrustedPiacVerifier();

  private TrustedPiacVerifier() {}

  public boolean verifiesLiveIdentity() { return false; }
}
