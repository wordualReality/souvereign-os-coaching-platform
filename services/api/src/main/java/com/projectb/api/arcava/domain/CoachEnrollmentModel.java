package com.projectb.api.arcava.domain;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import static com.projectb.api.arcava.domain.TenantModel.*;

/** Immutable ATC-04 AG-ARC-004/005 snapshots, not a mutable lifecycle or trusted grant. */
public final class CoachEnrollmentModel {
  private CoachEnrollmentModel() {}
  public enum AssignmentState { PENDING, ACTIVE, ENDED, REVOKED }
  public enum EnrollmentState { PENDING, ACTIVE, COMPLETED, CANCELLED, REVOKED }
  /** Knowledge metadata only: source does not enumerate assignment role values. */
  public enum RoleKnowledge { UNKNOWN, NOT_VERIFIED }

  public record AssignmentId(UUID value) {
    public AssignmentId { identity(value); }
    public static AssignmentId parse(String value) { return new AssignmentId(exact(value)); }
    public Namespace namespace() { return Namespace.ARCAVA; }
  }
  public record EnrollmentId(UUID value) {
    public EnrollmentId { identity(value); }
    public static EnrollmentId parse(String value) { return new EnrollmentId(exact(value)); }
    public Namespace namespace() { return Namespace.ARCAVA; }
  }
  /** Exact local JourneyVersion identity reference, not verified KDB publication evidence. */
  public record JourneyVersionRef(UUID value) {
    public JourneyVersionRef { identity(value); }
    public static JourneyVersionRef parse(String value) { return new JourneyVersionRef(exact(value)); }
    public Namespace namespace() { return Namespace.ARCAVA; }
  }

  public record CoachAssignment(AssignmentId id, TenantId tenantId, ClientId clientId,
                                PiacPrincipalRef coachPrincipalRef, RoleKnowledge role,
                                AssignmentState status, Instant validFrom, Optional<Instant> validUntil) {
    public CoachAssignment {
      required(id); required(tenantId); required(clientId); required(coachPrincipalRef);
      required(role); required(status); required(validFrom); required(validUntil);
      validUntil.ifPresent(end -> {
        if (!end.isAfter(validFrom)) throw invalid("nonempty ordered validity required");
      });
    }
    public void requireScope(TenantId expectedTenant, ClientId expectedClient) {
      scope(tenantId, clientId, expectedTenant, expectedClient);
    }
    public void requireClient(ClientProfile client) {
      required(client); requireScope(client.tenantId(), client.id());
    }
    /** Temporal check only. Success never proves role, ACTIVE eligibility or external authority. */
    public void requireCurrentWindow(Instant at) {
      required(at);
      if (at.isBefore(validFrom) || validUntil.filter(end -> !at.isBefore(end)).isPresent())
        throw invalid("outside declared assignment window");
    }
    public Verification verification() { return Verification.NOT_VERIFIED; }
    @Override public String toString() { return "CoachAssignment[owner=ARCAVA,verification=NOT_VERIFIED]"; }
  }

  public record Enrollment(EnrollmentId id, TenantId tenantId, ClientId clientId,
                           JourneyVersionRef journeyVersionRef, EnrollmentState status, Instant effectiveAt) {
    public Enrollment {
      required(id); required(tenantId); required(clientId); required(journeyVersionRef);
      required(status); required(effectiveAt);
    }
    public void requireScope(TenantId expectedTenant, ClientId expectedClient) {
      scope(tenantId, clientId, expectedTenant, expectedClient);
    }
    public void requireClient(ClientProfile client) {
      required(client); requireScope(client.tenantId(), client.id());
    }
    public Verification verification() { return Verification.NOT_VERIFIED; }
    @Override public String toString() { return "Enrollment[owner=ARCAVA,verification=NOT_VERIFIED]"; }
  }

  private static void scope(TenantId tenant, ClientId client, TenantId expectedTenant, ClientId expectedClient) {
    if (!tenant.equals(expectedTenant) || !client.equals(expectedClient)) throw invalid("owner client scope mismatch");
  }
  private static void required(Object value) {
    if (value == null) throw invalid("required model value missing");
  }
  private static void identity(UUID value) {
    if (value == null || value.equals(new UUID(0, 0))) throw invalid("non-nil identity required");
  }
  private static UUID exact(String value) {
    try {
      UUID id = UUID.fromString(value); identity(id);
      if (!id.toString().equals(value)) throw invalid("canonical identity required");
      return id;
    } catch (RuntimeException malformed) { throw invalid("canonical non-nil identity required"); }
  }
  private static IllegalArgumentException invalid(String message) { return new IllegalArgumentException(message); }
}
