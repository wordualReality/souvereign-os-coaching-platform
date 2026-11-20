package com.projectb.api.arcava.security;

import java.time.Instant;
import java.util.UUID;

/** Backend evidence model. No public constructor, HTTP binder or live issuer exists. */
public final class TrustedRequestContext {
  public enum Role { CLIENT, COACH, TENANT_ADMIN, ARCAVA_APPLICATION_SERVICE, PROVIDER_ADAPTER,
    COMPOSITION_SERVICE, AUDIT_READER, MIGRATION_OWNER }
  public enum Purpose { COACHING_SUPPORT, SELF_ACCESS, UNKNOWN }
  public enum Operation { SENSITIVE_CLIENT_READ, UNKNOWN }
  public enum State { CURRENT, UNKNOWN, DENIED, REVOKED, STALE }
  public enum Gate { SESSION, TENANT_MEMBERSHIP, ACCESS, ASSIGNMENT, CONSENT, SHARE, ENTITLEMENT }
  public record Request(UUID claimedPrincipal, UUID tenant, UUID subject, UUID resource,
                        Purpose purpose, Operation operation, long revision) {}
  public record Evidence(Gate gate, UUID principal, UUID tenant, UUID subject, UUID resource,
                         Purpose purpose, Operation operation, String policyRef, String decisionRef,
                         long revision, State state, Instant effectiveAt, Instant expiresAt,
                         Instant revokedAt) {}

  final UUID principal;
  final UUID tenant;
  final UUID subject;
  final UUID resource;
  final UUID authSession;
  final Role role;
  final Purpose purpose;
  final Operation operation;
  final long revision;
  final java.util.Map<Gate, Evidence> evidence;

  // Package-private construction is reserved for a future reviewed backend adapter.
  // Current repository construction occurs only in SYNTHETIC_TEST_ONLY fixtures.
  TrustedRequestContext(UUID principal, UUID tenant, UUID subject, UUID resource, UUID authSession,
                        Role role, Purpose purpose, Operation operation, long revision,
                        java.util.Map<Gate, Evidence> evidence) {
    this.principal=principal; this.tenant=tenant; this.subject=subject; this.resource=resource;
    this.authSession=authSession; this.role=role; this.purpose=purpose; this.operation=operation;
    this.revision=revision; this.evidence=java.util.Map.copyOf(evidence);
  }
}
