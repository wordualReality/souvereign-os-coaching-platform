package com.projectb.api.arcava.domain;

import com.projectb.api.domain.JourneyJournal.EnrollmentLink;
import java.util.Objects;
import java.util.UUID;
import com.projectb.api.arcava.domain.TenantModel.TenantId;
import com.projectb.api.arcava.domain.TenantModel.ClientId;
import com.projectb.api.arcava.domain.CoachEnrollmentModel.AssignmentId;
import com.projectb.api.arcava.domain.CoachEnrollmentModel.EnrollmentId;
import com.projectb.api.arcava.domain.CoachEnrollmentModel.JourneyVersionRef;

/** Typed snapshot of existing journal fields, not a new enrollment lifecycle or authority. */
public record ClientRelationshipModel(UUID tenantId, UUID clientId, UUID versionId,
                                      UUID assignmentId, UUID enrollmentId) {
  public ClientRelationshipModel {
    for (UUID id : new UUID[]{tenantId, clientId, versionId, assignmentId, enrollmentId}) {
      Objects.requireNonNull(id);
      if (id.equals(new UUID(0, 0))) throw new IllegalArgumentException("identity required");
    }
  }

  public static ClientRelationshipModel from(EnrollmentLink link) {
    Objects.requireNonNull(link);
    return new ClientRelationshipModel(exact(link.tenantId()), exact(link.clientId()),
        exact(link.versionId()), exact(link.assignmentId()), exact(link.enrollmentId()));
  }

  /** Pure identity mapping only; does not establish current storage linkage or authorize a read. */
  public JournalIdentity typedIdentity() {
    return new JournalIdentity(new TenantId(tenantId), new ClientId(clientId),
        new JourneyVersionRef(versionId), new AssignmentId(assignmentId), new EnrollmentId(enrollmentId));
  }

  /** Same five fields and order as the source. No role, state, principal, time or trust evidence. */
  public record JournalIdentity(TenantId tenantId, ClientId clientId, JourneyVersionRef versionId,
                                AssignmentId assignmentId, EnrollmentId enrollmentId) {
    public JournalIdentity {
      if (tenantId == null || clientId == null || versionId == null || assignmentId == null || enrollmentId == null)
        throw new IllegalArgumentException("complete typed journal identity required");
    }
    public void requireScope(TenantId expectedTenant, ClientId expectedClient) {
      if (!tenantId.equals(expectedTenant) || !clientId.equals(expectedClient))
        throw new IllegalArgumentException("journal identity scope mismatch");
    }
    public void requireSameIdentity(JournalIdentity expected) {
      if (!equals(expected)) throw new IllegalArgumentException("journal identity mismatch");
    }
    @Override public String toString() { return "JournalIdentity[references=redacted]"; }
  }

  private static UUID exact(String value) {
    UUID id = UUID.fromString(value);
    if (!id.toString().equals(value)) throw new IllegalArgumentException("canonical UUID required");
    return id;
  }
}
