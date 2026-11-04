package com.projectb.api.arcava.repositories;

import com.projectb.api.arcava.domain.ClientRelationshipModel;
import com.projectb.api.domain.JourneyJournal;
import com.projectb.api.domain.JourneyJournal.EnrollmentLink;
import java.util.Objects;
import java.util.UUID;

/** Local read-only adapter. Lookup is storage, never an authorization source. */
public final class ClientRelationshipRepository {
  @FunctionalInterface public interface EnrollmentLookup { EnrollmentLink enrollment(UUID id); }
  public enum Status { FOUND, NOT_FOUND, INVALID_STORED_DATA, UNAVAILABLE }
  public record Lookup(Status status, ClientRelationshipModel model) {}
  private final EnrollmentLookup lookup;

  public ClientRelationshipRepository(JourneyJournal journal) {
    this(Objects.requireNonNull(journal)::enrollment);
  }

  /** Backend storage seam, also used by fault-injection tests; grants no trust. */
  public ClientRelationshipRepository(EnrollmentLookup lookup) {
    this.lookup = Objects.requireNonNull(lookup);
  }

  public Lookup enrollment(UUID id) {
    if (id == null) return new Lookup(Status.INVALID_STORED_DATA, null);
    EnrollmentLink link;
    try { link = lookup.enrollment(id); }
    catch (RuntimeException failure) { return new Lookup(Status.UNAVAILABLE, null); }
    if (link == null) return new Lookup(Status.NOT_FOUND, null);
    try { return new Lookup(Status.FOUND, ClientRelationshipModel.from(link)); }
    catch (RuntimeException malformed) { return new Lookup(Status.INVALID_STORED_DATA, null); }
  }
}
