package com.projectb.api.arcava.security;

import static com.projectb.api.arcava.security.TrustedRequestContext.*;

/** Only the two explicitly supported sensitive-read domain scopes are implemented. */
public final class RoleScopePolicy {
  boolean permits(TrustedRequestContext context) {
    return (context.role==Role.COACH && context.purpose==Purpose.COACHING_SUPPORT)
        || (context.role==Role.CLIENT && context.principal.equals(context.subject)
            && context.purpose==Purpose.SELF_ACCESS);
  }
}
