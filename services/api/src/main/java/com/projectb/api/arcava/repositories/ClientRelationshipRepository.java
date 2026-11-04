package com.projectb.api.arcava.repositories;

import com.projectb.api.arcava.domain.ClientRelationshipModel;
import com.projectb.api.domain.JourneyJournal;
import com.projectb.api.domain.JourneyJournal.EnrollmentLink;
import com.projectb.api.domain.JourneyJournal.Projection;
import java.util.Objects;
import java.util.UUID;

/** Local read-only adapter. Lookup is storage, never an authorization source. */
public final class ClientRelationshipRepository {
  /** Immutable storage observations, not a trusted publication/identity attestation. */
  public record EnrollmentSnapshot(EnrollmentLink enrollment, Projection projection) {}
  @FunctionalInterface public interface SnapshotLookup { EnrollmentSnapshot enrollment(UUID id); }
  public enum Status { FOUND, NOT_FOUND, INVALID_STORED_DATA, UNAVAILABLE }
  public record Lookup(Status status, ClientRelationshipModel model) {}
  private final SnapshotLookup lookup;

  public ClientRelationshipRepository(JourneyJournal journal) {
    Objects.requireNonNull(journal);
    this.lookup = id -> {
      // Both journal methods and withdraw synchronize on this exact monitor.
      // Snapshot values are immutable records; no PUBLISHED result is cached.
      synchronized (journal) {
        EnrollmentLink link = journal.enrollment(id);
        if (link == null) return new EnrollmentSnapshot(null, null);
        UUID version;
        try { version = UUID.fromString(link.versionId()); }
        catch (RuntimeException malformed) { return new EnrollmentSnapshot(link, null); }
        return new EnrollmentSnapshot(link, journal.projection(version));
      }
    };
  }

  /** Backend storage seam, also used by fault-injection tests; grants no trust. */
  public ClientRelationshipRepository(SnapshotLookup lookup) {
    this.lookup = Objects.requireNonNull(lookup);
  }

  public Lookup enrollment(UUID id) {
    if (id == null) return new Lookup(Status.INVALID_STORED_DATA, null);
    EnrollmentSnapshot snapshot;
    try { snapshot = lookup.enrollment(id); }
    catch (RuntimeException failure) { return new Lookup(Status.UNAVAILABLE, null); }
    if (snapshot == null) return new Lookup(Status.UNAVAILABLE, null);
    EnrollmentLink link = snapshot.enrollment();
    if (link == null) return new Lookup(Status.NOT_FOUND, null);
    ClientRelationshipModel model;
    try { model = ClientRelationshipModel.from(link); }
    catch (RuntimeException malformed) { return new Lookup(Status.INVALID_STORED_DATA, null); }
    Projection projection = snapshot.projection();
    // Missing, foreign, malformed, withdrawn and unknown states share a safe absence response.
    if (projection == null || !model.tenantId().toString().equals(projection.tenantId())
        || !model.versionId().toString().equals(projection.versionId())
        || !canonicalIdentity(projection.journeyId())
        || !"PUBLISHED".equals(projection.publicationState())) return new Lookup(Status.NOT_FOUND, null);
    return new Lookup(Status.FOUND, model);
  }

  private static boolean canonicalIdentity(String value) {
    try {
      UUID id = UUID.fromString(value);
      return !id.equals(new UUID(0, 0)) && id.toString().equals(value);
    } catch (RuntimeException malformed) { return false; }
  }
}
