package com.projectb.api.arcava.domain;

import com.projectb.api.domain.JourneyJournal.EnrollmentLink;
import java.util.Objects;
import java.util.UUID;

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

  private static UUID exact(String value) {
    UUID id = UUID.fromString(value);
    if (!id.toString().equals(value)) throw new IllegalArgumentException("canonical UUID required");
    return id;
  }
}
