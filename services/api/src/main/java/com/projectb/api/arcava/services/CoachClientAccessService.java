package com.projectb.api.arcava.services;

import com.projectb.api.arcava.security.OwnerGuard;
import com.projectb.api.arcava.security.TrustedRequestContext.Request;
import java.util.Objects;

/** Product-domain sensitive-read authorization; returns no client resource payload. */
public final class CoachClientAccessService {
  private final OwnerGuard guard;
  public CoachClientAccessService(OwnerGuard guard) { this.guard=Objects.requireNonNull(guard); }
  public OwnerGuard.Decision authorizeSensitiveClientRead(Request request) {
    return guard.authorize(request);
  }
}
