package com.projectb.api.arcava.domain;

import java.math.BigInteger;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

/**
 * Owner-local immutable identity snapshots (ATC-04 AG-ARC-001/003, EN-ARC-002).
 * No activation, state transition, authenticated provenance or access decision API.
 */
public final class TenantModel {
  private TenantModel() {}

  public enum Namespace { ARCAVA, PIAC }
  /** Only the states actually defined by SM-ARC-01. A snapshot is not an activation. */
  public enum TenantState { PROVISIONING, ACTIVE, SUSPENDED, CLOSED }
  /** Knowledge metadata, NOT invented ClientProfile/TenantMembership lifecycle states. */
  public enum UnresolvedLifecycle { UNKNOWN, NOT_VERIFIED }
  public enum Verification { NOT_VERIFIED }

  public record TenantId(UUID value) {
    public TenantId { identity(value); }
    public static TenantId parse(String value) { return new TenantId(exact(value)); }
    public Namespace namespace() { return Namespace.ARCAVA; }
  }
  public record ClientId(UUID value) {
    public ClientId { identity(value); }
    public static ClientId parse(String value) { return new ClientId(exact(value)); }
    public Namespace namespace() { return Namespace.ARCAVA; }
  }
  public record MembershipId(UUID value) {
    public MembershipId { identity(value); }
    public static MembershipId parse(String value) { return new MembershipId(exact(value)); }
    public Namespace namespace() { return Namespace.ARCAVA; }
  }
  /** A reference to PIAC-owned identity, never a verified PIAC identity or session. */
  public record PiacPrincipalRef(UUID value) {
    public PiacPrincipalRef { identity(value); }
    public static PiacPrincipalRef parse(String value) { return new PiacPrincipalRef(exact(value)); }
    public Namespace namespace() { return Namespace.PIAC; }
    @Override public String toString() { return "PiacPrincipalRef[redacted]"; }
  }
  public record ArcavaConfigRef(UUID value) {
    public ArcavaConfigRef { identity(value); }
    public Namespace namespace() { return Namespace.ARCAVA; }
  }
  /** Opaque reference only; contains no imported private profile body. */
  public record SensitiveProfileRef(String value) {
    public SensitiveProfileRef { text(value); }
    @Override public String toString() { return "SensitiveProfileRef[redacted]"; }
  }

  public record BusinessTenant(TenantId id, String displayName, Optional<TenantState> status,
                               Optional<ArcavaConfigRef> brandingConfigRef,
                               Optional<String> legalScopeRef) {
    public BusinessTenant {
      required(id); text(displayName); required(status); required(brandingConfigRef);
      required(legalScopeRef); legalScopeRef.ifPresent(TenantModel::text);
    }
    /** Even an ACTIVE source-state label supplies no authenticated activation provenance. */
    public Verification verification() { return Verification.NOT_VERIFIED; }
    public Optional<UnresolvedLifecycle> unresolvedStatus() {
      return status.isEmpty() ? Optional.of(UnresolvedLifecycle.UNKNOWN) : Optional.empty();
    }
    @Override public String toString() { return "BusinessTenant[owner=ARCAVA,verification=NOT_VERIFIED]"; }
  }

  public record ClientProfile(ClientId id, TenantId tenantId,
                              Optional<PiacPrincipalRef> principalRef,
                              UnresolvedLifecycle profileStatus,
                              Optional<SensitiveProfileRef> privateProfileRef) {
    public ClientProfile {
      required(id); required(tenantId); required(principalRef); required(profileStatus);
      required(privateProfileRef);
    }
    /** Structural comparison only; successful scope matching never grants access. */
    public void requireScope(TenantId expectedTenant, ClientId expectedClient) {
      if (!tenantId.equals(expectedTenant) || !id.equals(expectedClient)) throw invalid("client scope mismatch");
    }
    public Verification verification() { return Verification.NOT_VERIFIED; }
    @Override public String toString() { return "ClientProfile[owner=ARCAVA,verification=NOT_VERIFIED]"; }
  }

  /** Minimal EN-ARC-002 identity/provenance snapshot; unknown role/validity is not synthesized. */
  public record TenantMembership(MembershipId id, TenantId parentId, PiacPrincipalRef principalRef,
                                 Instant createdAt, Optional<BigInteger> revision,
                                 UnresolvedLifecycle lifecycle) {
    public TenantMembership {
      required(id); required(parentId); required(principalRef); required(createdAt);
      required(revision); required(lifecycle);
      revision.ifPresent(value -> {
        if (value.signum() < 0 || value.bitLength() > 64) throw invalid("revision outside uint64");
      });
    }
    public void requireTenant(TenantId expectedTenant) {
      if (!parentId.equals(expectedTenant)) throw invalid("membership scope mismatch");
    }
    public Verification verification() { return Verification.NOT_VERIFIED; }
    @Override public String toString() { return "TenantMembership[owner=ARCAVA,verification=NOT_VERIFIED]"; }
  }

  private static void required(Object value) {
    if (value == null) throw invalid("required model value missing");
  }
  private static void text(String value) {
    if (value == null || value.isBlank()) throw invalid("nonblank reference or label required");
  }
  private static void identity(UUID value) {
    if (value == null || value.equals(new UUID(0, 0))) throw invalid("non-nil identity required");
  }
  private static UUID exact(String value) {
    try {
      UUID id = UUID.fromString(value);
      identity(id);
      if (!id.toString().equals(value)) throw invalid("canonical identity required");
      return id;
    } catch (RuntimeException malformed) { throw invalid("canonical non-nil identity required"); }
  }
  private static IllegalArgumentException invalid(String message) { return new IllegalArgumentException(message); }
}
