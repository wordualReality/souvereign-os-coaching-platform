package com.projectb.api.arcava.services;

import com.projectb.api.arcava.repositories.ClientRelationshipRepository;
import com.projectb.api.arcava.security.OwnerGuard;
import com.projectb.api.arcava.security.TrustedRequestContext.Request;
import java.util.Objects;
import java.util.UUID;

/** Guarded local enrollment read. No HTTP route, live identity adapter or SQL integration. */
public final class ArcavaAccessService {
  public enum Status { ALLOWED, ACCESS_DENIED, NOT_FOUND, STORED_DATA_INVALID, READ_UNAVAILABLE }
  public record EnrollmentView(UUID enrollmentId, UUID journeyVersionId) {}
  public record Result(Status status, EnrollmentView view) {
    public Result {
      Objects.requireNonNull(status);
      if ((status == Status.ALLOWED) != (view != null))
        throw new IllegalArgumentException("payload only for allowed result");
    }
  }
  private final OwnerGuard guard;
  private final ClientRelationshipRepository repository;

  public ArcavaAccessService(OwnerGuard guard, ClientRelationshipRepository repository) {
    this.guard = Objects.requireNonNull(guard);
    this.repository = Objects.requireNonNull(repository);
  }

  public Result readEnrollment(Request request) {
    // Mandatory before even testing resource existence. Caller fields never grant authority.
    if (!guard.authorize(request).allowed()) return new Result(Status.ACCESS_DENIED, null);
    var stored = repository.enrollment(request.resource());
    switch (stored.status()) {
      case NOT_FOUND: return new Result(Status.NOT_FOUND, null);
      case INVALID_STORED_DATA: return new Result(Status.STORED_DATA_INVALID, null);
      case UNAVAILABLE: return new Result(Status.READ_UNAVAILABLE, null);
      case FOUND: break;
    }
    var model = stored.model();
    // A valid guard decision alone cannot authorize a differently bound stored object.
    if (!request.tenant().equals(model.tenantId()) || !request.subject().equals(model.clientId())
        || !request.resource().equals(model.enrollmentId())) return new Result(Status.NOT_FOUND, null);
    return new Result(Status.ALLOWED, new EnrollmentView(model.enrollmentId(), model.versionId()));
  }
}
