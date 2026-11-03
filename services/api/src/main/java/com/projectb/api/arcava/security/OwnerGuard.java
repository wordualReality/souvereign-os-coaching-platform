package com.projectb.api.arcava.security;

import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.Objects;
import static com.projectb.api.arcava.security.TrustedRequestContext.*;

/** Owner-domain policy only. The public production path has no admitted PIAC adapter. */
public final class OwnerGuard {
  public enum Reason { ALLOW_SYNTHETIC_DOMAIN_SCOPE, REQUEST_INVALID, PIAC_NOT_CONNECTED,
    TRUST_UNAVAILABLE, CONTEXT_MISMATCH, ROLE_SCOPE_DENIED, EVIDENCE_MISSING,
    EVIDENCE_BINDING_MISMATCH, EVIDENCE_NOT_CURRENT, EVIDENCE_TIME_INVALID }
  public record Decision(boolean allowed, Reason reason, List<String> decisionReferences) {
    public Decision { decisionReferences=List.copyOf(decisionReferences); }
  }
  @FunctionalInterface interface ContextSource { TrustedRequestContext resolve(Request request); }
  private final ContextSource source;
  private final Clock clock;
  private final RoleScopePolicy roles=new RoleScopePolicy();

  public OwnerGuard(Clock clock) { this(clock, request -> null); }
  OwnerGuard(Clock clock, ContextSource source) {
    this.clock=Objects.requireNonNull(clock); this.source=Objects.requireNonNull(source);
  }
  private static Decision deny(Reason reason) { return new Decision(false,reason,List.of()); }
  private static boolean blank(String value) { return value==null || value.isBlank(); }

  public Decision authorize(Request request) {
    if (request==null || request.claimedPrincipal()==null || request.tenant()==null
        || request.subject()==null || request.resource()==null || request.revision()<1
        || request.purpose()==null || request.purpose()==Purpose.UNKNOWN
        || request.operation()!=Operation.SENSITIVE_CLIENT_READ) return deny(Reason.REQUEST_INVALID);
    TrustedRequestContext context;
    try { context=source.resolve(request); }
    catch (RuntimeException failure) { return deny(Reason.TRUST_UNAVAILABLE); }
    if (context==null) return deny(Reason.PIAC_NOT_CONNECTED);
    if (context.authSession==null || context.role==null
        || !request.claimedPrincipal().equals(context.principal)
        || !request.tenant().equals(context.tenant) || !request.subject().equals(context.subject)
        || !request.resource().equals(context.resource) || request.purpose()!=context.purpose
        || request.operation()!=context.operation || request.revision()!=context.revision)
      return deny(Reason.CONTEXT_MISMATCH);
    if (!roles.permits(context)) return deny(Reason.ROLE_SCOPE_DENIED);
    Instant now=clock.instant();
    java.util.ArrayList<String> references=new java.util.ArrayList<>();
    for (Gate gate:Gate.values()) {
      if (gate==Gate.ASSIGNMENT && context.role==Role.CLIENT) continue;
      Evidence proof=context.evidence.get(gate);
      if (proof==null) return deny(Reason.EVIDENCE_MISSING);
      if (proof.gate()!=gate || !Objects.equals(proof.principal(),context.principal)
          || !Objects.equals(proof.tenant(),context.tenant) || !Objects.equals(proof.subject(),context.subject)
          || !Objects.equals(proof.resource(),context.resource) || proof.purpose()!=context.purpose
          || proof.operation()!=context.operation || proof.revision()!=context.revision
          || blank(proof.policyRef()) || blank(proof.decisionRef())) return deny(Reason.EVIDENCE_BINDING_MISMATCH);
      if (proof.state()!=State.CURRENT) return deny(Reason.EVIDENCE_NOT_CURRENT);
      if (proof.effectiveAt()==null || proof.expiresAt()==null || now.isBefore(proof.effectiveAt())
          || !now.isBefore(proof.expiresAt()) || (proof.revokedAt()!=null && !now.isBefore(proof.revokedAt())))
        return deny(Reason.EVIDENCE_TIME_INVALID);
      references.add(proof.decisionRef());
    }
    return new Decision(true,Reason.ALLOW_SYNTHETIC_DOMAIN_SCOPE,references);
  }
}
