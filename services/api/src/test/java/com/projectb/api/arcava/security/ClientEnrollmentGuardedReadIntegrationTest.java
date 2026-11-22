package com.projectb.api.arcava.security;

import com.projectb.api.arcava.repositories.ClientRelationshipRepository;
import com.projectb.api.arcava.services.ArcavaAccessService;
import com.projectb.api.arcava.services.ArcavaAccessService.Result;
import com.projectb.api.domain.JourneyJournal;
import com.projectb.api.domain.JourneyJournal.EnrollmentLink;
import com.projectb.api.domain.JourneyJournal.Projection;
import com.projectb.api.arcava.repositories.ClientRelationshipRepository.EnrollmentSnapshot;
import com.projectb.api.domain.JourneyKernel;
import com.projectb.api.domain.JourneyKernel.AssignmentView;
import com.projectb.api.arcava.domain.ClientRelationshipModel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static com.projectb.api.arcava.security.TrustedRequestContext.*;
import static com.projectb.api.arcava.services.ArcavaAccessService.Status.*;
import static org.junit.jupiter.api.Assertions.*;

class ClientEnrollmentGuardedReadIntegrationTest {
  static final Instant NOW = Instant.parse("2026-11-04T12:00:00Z");
  static final Clock CLOCK = Clock.fixed(NOW, ZoneOffset.UTC);
  static final UUID COACH = new UUID(0, 1), TENANT = new UUID(0, 2), CLIENT = new UUID(0, 3),
      SESSION = new UUID(0, 5), OTHER = new UUID(0, 99);
  @TempDir Path temp;
  Path path;
  JourneyJournal journal;
  EnrollmentLink link;
  UUID enrollment;

  @BeforeEach void persistRealLifecycleWithSyntheticAuthority() throws Exception {
    path = temp.resolve("journey.jsonl");
    journal = JourneyJournal.open(path);
    link = populate(journal, CLIENT.toString());
    enrollment = UUID.fromString(link.enrollmentId());
  }

  /** SYNTHETIC_TEST_ONLY: kernel consent and canonical pins are doubles, not PIAC/KDB proof. */
  static EnrollmentLink populate(JourneyJournal journal, String client) throws Exception {
    var actor = new JourneyKernel.Actor(TENANT.toString(), COACH.toString(), JourneyKernel.Role.COACH);
    var draft = journal.createDraft(actor, "synthetic enrollment", "create-test");
    var updated = journal.updateDraft(actor, draft.draftId(), draft.revision(), "synthetic updated",
        List.of(new JourneyKernel.Step("test-step", "test-only",
            new JourneyKernel.CanonicalPin("synthetic-version", "a".repeat(64), true, true))), "[]");
    var version = journal.publish(actor, draft.draftId(), updated.revision(), "publish-test");
    var assigned = journal.assign(actor, client, version.journeyVersionId(), true, "assign-test");
    UUID id = UUID.nameUUIDFromBytes(("enrollment/" + assigned.assignmentId())
        .getBytes(java.nio.charset.StandardCharsets.UTF_8));
    return journal.enrollment(id);
  }

  /** SYNTHETIC_TEST_ONLY. No production trust factory, bean, header or verifier registration. */
  static TrustedRequestContext synthetic(Role role, UUID tenant, UUID client, UUID resource) {
    UUID principal = role == Role.CLIENT ? client : COACH;
    Purpose purpose = role == Role.CLIENT ? Purpose.SELF_ACCESS : Purpose.COACHING_SUPPORT;
    Map<Gate, Evidence> evidence = new EnumMap<>(Gate.class);
    for (Gate gate : Gate.values()) {
      if (role == Role.CLIENT && gate == Gate.ASSIGNMENT) continue;
      evidence.put(gate, new Evidence(gate, principal, tenant, client, resource, purpose,
          Operation.SENSITIVE_CLIENT_READ, "synthetic-policy", "synthetic-" + gate, 1,
          State.CURRENT, NOW.minusSeconds(60), NOW.plusSeconds(60), null));
    }
    return new TrustedRequestContext(principal, tenant, client, resource, SESSION, role,
        purpose, Operation.SENSITIVE_CLIENT_READ, 1, evidence);
  }
  TrustedRequestContext coach() { return synthetic(Role.COACH, TENANT, CLIENT, enrollment); }
  static Request request(TrustedRequestContext c) {
    return new Request(c.principal, c.tenant, c.subject, c.resource, c.purpose, c.operation, c.revision);
  }
  static TrustedRequestContext proof(TrustedRequestContext c, Gate gate, Evidence value) {
    Map<Gate, Evidence> evidence = new EnumMap<>(c.evidence);
    if (value == null) evidence.remove(gate); else evidence.put(gate, value);
    return new TrustedRequestContext(c.principal, c.tenant, c.subject, c.resource, c.authSession,
        c.role, c.purpose, c.operation, c.revision, evidence);
  }
  static ArcavaAccessService service(TrustedRequestContext c, ClientRelationshipRepository repository) {
    return new ArcavaAccessService(new OwnerGuard(CLOCK, ignored -> c), repository);
  }
  Result read(TrustedRequestContext c, JourneyJournal source) {
    return service(c, new ClientRelationshipRepository(source)).readEnrollment(request(c));
  }
  void assertBeforeAndAfterReplay(TrustedRequestContext c, ArcavaAccessService.Status status) throws Exception {
    byte[] before = Files.readAllBytes(path);
    Result first = read(c, journal);
    assertEquals(status, first.status());
    assertEquals(first, read(c, JourneyJournal.open(path)));
    if (status != ALLOWED) assertNull(first.view());
    assertArrayEquals(before, Files.readAllBytes(path));
  }
  void assertGuardDeniesBeforeLookup(TrustedRequestContext c, Request request) throws Exception {
    byte[] before = Files.readAllBytes(path);
    for (var source : List.of(journal, JourneyJournal.open(path))) {
      AtomicInteger calls = new AtomicInteger();
      var repository = new ClientRelationshipRepository(id -> {
        calls.incrementAndGet(); return snapshot(source, id);
      });
      var result = service(c, repository).readEnrollment(request);
      assertEquals(ACCESS_DENIED, result.status()); assertNull(result.view());
      assertEquals(0, calls.get(), "guard must precede storage/existence lookup");
      assertFalse(result.toString().contains("synthetic-policy"));
    }
    assertArrayEquals(before, Files.readAllBytes(path));
  }

  static EnrollmentSnapshot snapshot(JourneyJournal source, UUID id) {
    synchronized (source) {
      var entry = source.enrollment(id);
      return new EnrollmentSnapshot(entry, entry == null ? null : source.projection(UUID.fromString(entry.versionId())),
          entry == null ? null : source.assignmentSnapshot(UUID.fromString(entry.assignmentId())));
    }
  }

  @Test void assignedCoachReadsPersistedEnrollmentAndExactReplay() throws Exception {
    assertBeforeAndAfterReplay(coach(), ALLOWED);
    assertEquals(new ArcavaAccessService.EnrollmentView(enrollment, UUID.fromString(link.versionId())),
        read(coach(), journal).view());
    assertEquals(link, JourneyJournal.open(path).enrollment(enrollment));
    assertEquals(4, Files.readAllLines(path).size(), "real create/update/publish/assign");
  }
  @Test void ownClientReadsWithoutCoachAssignmentAfterReplay() throws Exception {
    var c = synthetic(Role.CLIENT, TENANT, CLIENT, enrollment);
    assertFalse(c.evidence.containsKey(Gate.ASSIGNMENT));
    assertBeforeAndAfterReplay(c, ALLOWED);
  }
  @Test void wrongCallerTenantClientAndResourceDenyBeforeLookup() throws Exception {
    var c = coach();
    for (Request r : List.of(
        new Request(COACH, OTHER, CLIENT, enrollment, c.purpose, c.operation, 1),
        new Request(COACH, TENANT, OTHER, enrollment, c.purpose, c.operation, 1),
        new Request(COACH, TENANT, CLIENT, OTHER, c.purpose, c.operation, 1),
        new Request(OTHER, TENANT, CLIENT, enrollment, c.purpose, c.operation, 1)))
      assertGuardDeniesBeforeLookup(c, r);
  }
  @Test void storedTenantAndClientMismatchAreIndistinguishableFromAbsent() throws Exception {
    assertBeforeAndAfterReplay(synthetic(Role.COACH, OTHER, CLIENT, enrollment), NOT_FOUND);
    assertBeforeAndAfterReplay(synthetic(Role.COACH, TENANT, OTHER, enrollment), NOT_FOUND);
    assertBeforeAndAfterReplay(synthetic(Role.COACH, TENANT, CLIENT, OTHER), NOT_FOUND);
  }
  @Test void substitutedStoredEnrollmentIdCannotReturnPayload() {
    var swapped = new EnrollmentLink(link.tenantId(), link.clientId(), link.versionId(), link.assignmentId(), OTHER.toString());
    var result = service(coach(), new ClientRelationshipRepository(id -> new EnrollmentSnapshot(swapped, journal.projection(UUID.fromString(link.versionId())), journal.assignmentSnapshot(UUID.fromString(link.assignmentId()))))).readEnrollment(request(coach()));
    assertEquals(NOT_FOUND, result.status()); assertNull(result.view());
  }
  @Test void everyMissingIndependentGateDeniesBeforeLookupAndAfterReplay() throws Exception {
    for (Gate gate : Gate.values()) {
      var c = proof(coach(), gate, null);
      assertGuardDeniesBeforeLookup(c, request(c));
    }
  }
  @Test void expiredRevokedUnknownAndStaleGatesDenyBeforeLookupAndAfterReplay() throws Exception {
    for (Gate gate : Gate.values()) for (String variant : List.of("expired", "revoked", "unknown", "stale", "denied")) {
      var c = coach(); var p = c.evidence.get(gate);
      var changed = new Evidence(p.gate(), p.principal(), p.tenant(), p.subject(), p.resource(),
          p.purpose(), p.operation(), p.policyRef(), p.decisionRef(), 1,
          switch (variant) { case "unknown" -> State.UNKNOWN; case "stale" -> State.STALE;
            case "denied" -> State.DENIED; default -> State.CURRENT; },
          p.effectiveAt(), variant.equals("expired") ? NOW : p.expiresAt(),
          variant.equals("revoked") ? NOW : null);
      var invalid = proof(c, gate, changed);
      assertGuardDeniesBeforeLookup(invalid, request(invalid));
    }
  }
  @Test void tenantAdminAndServiceCannotBypassRepositoryGuard() throws Exception {
    for (Role role : Role.values()) if (role != Role.COACH && role != Role.CLIENT) {
      var c = synthetic(role, TENANT, CLIENT, enrollment);
      assertGuardDeniesBeforeLookup(c, request(c));
    }
  }
  @Test void noLivePiacNeverLooksUpEvenAnExistingEnrollment() throws Exception {
    byte[] before = Files.readAllBytes(path);
    AtomicInteger calls = new AtomicInteger();
    var repository = new ClientRelationshipRepository(id -> { calls.incrementAndGet(); return snapshot(journal, id); });
    var result = new ArcavaAccessService(new OwnerGuard(CLOCK), repository).readEnrollment(request(coach()));
    assertEquals(ACCESS_DENIED, result.status()); assertNull(result.view()); assertEquals(0, calls.get());
    assertArrayEquals(before, Files.readAllBytes(path));
  }
  @Test void nullAndUnknownRequestsDoNotLookup() throws Exception {
    var c = coach();
    assertGuardDeniesBeforeLookup(c, null);
    assertGuardDeniesBeforeLookup(c, new Request(COACH, TENANT, CLIENT, enrollment, Purpose.UNKNOWN, c.operation, 1));
    assertGuardDeniesBeforeLookup(c, new Request(COACH, TENANT, CLIENT, enrollment, c.purpose, Operation.UNKNOWN, 1));
  }
  @Test void malformedStoredFieldsFailClosedWithoutEchoingRawValues() {
    String[] valid = {link.tenantId(), link.clientId(), link.versionId(), link.assignmentId(), link.enrollmentId()};
    for (int field = 0; field < valid.length; field++) for (String invalid : Arrays.asList(null, "", "private-malicious-id", "1-1-1-1-1", new UUID(0, 0).toString())) {
      String[] values = valid.clone(); values[field] = invalid;
      var malformed = new EnrollmentLink(values[0], values[1], values[2], values[3], values[4]);
      var result = service(coach(), new ClientRelationshipRepository(id -> new EnrollmentSnapshot(malformed, journal.projection(UUID.fromString(link.versionId())), journal.assignmentSnapshot(UUID.fromString(link.assignmentId()))))).readEnrollment(request(coach()));
      assertEquals(STORED_DATA_INVALID, result.status()); assertNull(result.view());
      assertFalse(result.toString().contains("private-malicious-id"));
    }
  }
  @Test void unsupportedStoredClientFormatFromRealJournalDeniesAfterReplay() throws Exception {
    Path corruptPath = temp.resolve("unsupported-client.jsonl");
    var source = JourneyJournal.open(corruptPath);
    var bad = populate(source, "1-1-1-1-1"); // Existing kernel permits strings; typed boundary must reject.
    UUID resource = UUID.fromString(bad.enrollmentId());
    var c = synthetic(Role.COACH, TENANT, CLIENT, resource);
    byte[] before = Files.readAllBytes(corruptPath);
    for (var reopened : List.of(source, JourneyJournal.open(corruptPath))) {
      var result = read(c, reopened);
      assertEquals(STORED_DATA_INVALID, result.status()); assertNull(result.view());
    }
    assertArrayEquals(before, Files.readAllBytes(corruptPath));
  }
  @Test void storageFaultIsSafeAndCannotLeakException() {
    var repository = new ClientRelationshipRepository(id -> { throw new IllegalStateException("private-journal-data"); });
    var result = service(coach(), repository).readEnrollment(request(coach()));
    assertEquals(READ_UNAVAILABLE, result.status()); assertNull(result.view());
    assertFalse(result.toString().contains("private-journal-data"));
  }

  void withdraw() throws Exception {
    journal.withdraw(new JourneyKernel.Actor(TENANT.toString(), COACH.toString(), JourneyKernel.Role.COACH), UUID.fromString(link.versionId()));
  }

  @Test void withdrawalDeniesCoachAndSelfClientOnSameServiceAndAfterReplay() throws Exception {
    for (Role role : List.of(Role.COACH, Role.CLIENT)) {
      var c = synthetic(role, TENANT, CLIENT, enrollment);
      assertBeforeAndAfterReplay(c, ALLOWED);
    }
    var c = coach();
    var sameService = service(c, new ClientRelationshipRepository(journal));
    assertEquals(ALLOWED, sameService.readEnrollment(request(c)).status());
    withdraw();
    assertEquals(link, journal.enrollment(enrollment), "enrollment remains persisted");
    assertEquals("WITHDRAWN", journal.projection(UUID.fromString(link.versionId())).publicationState());
    for (Role role : List.of(Role.COACH, Role.CLIENT))
      assertBeforeAndAfterReplay(synthetic(role, TENANT, CLIENT, enrollment), NOT_FOUND);
    assertEquals(NOT_FOUND, sameService.readEnrollment(request(c)).status(), "must not cache PUBLISHED");
    byte[] after = Files.readAllBytes(path);
    withdraw(); // supported idempotent repeat, no new record
    assertArrayEquals(after, Files.readAllBytes(path));
    assertEquals(link, JourneyJournal.open(path).enrollment(enrollment));
  }

  @Test void allUnknownMissingAndMalformedPublicationSnapshotsFailClosed() {
    Projection p = journal.projection(UUID.fromString(link.versionId()));
    List<Projection> invalid = new ArrayList<>();
    invalid.add(null);
    for (String state : Arrays.asList(null, "", "UNKNOWN", "WITHDRAWN", "published", "private-state"))
      invalid.add(new Projection(p.tenantId(), p.journeyId(), p.versionId(), p.phasesJson(), p.contentHash(), p.publishedAt(), state));
    for (String id : Arrays.asList(null, "", "private-malformed-id", "1-1-1-1-1", OTHER.toString(), new UUID(0, 0).toString())) {
      invalid.add(new Projection(id, p.journeyId(), p.versionId(), p.phasesJson(), p.contentHash(), p.publishedAt(), "PUBLISHED"));
      invalid.add(new Projection(p.tenantId(), p.journeyId(), id, p.phasesJson(), p.contentHash(), p.publishedAt(), "PUBLISHED"));
    }
    for (String id : Arrays.asList(null, "", "private-malformed-id", "1-1-1-1-1", new UUID(0, 0).toString()))
      invalid.add(new Projection(p.tenantId(), id, p.versionId(), p.phasesJson(), p.contentHash(), p.publishedAt(), "PUBLISHED"));
    for (Projection value : invalid) {
      var result = service(coach(), new ClientRelationshipRepository(id -> new EnrollmentSnapshot(link, value, journal.assignmentSnapshot(UUID.fromString(link.assignmentId()))))).readEnrollment(request(coach()));
      assertEquals(NOT_FOUND, result.status()); assertNull(result.view());
      assertFalse(result.toString().contains("private"));
    }
    var missing = service(coach(), new ClientRelationshipRepository(id -> null)).readEnrollment(request(coach()));
    assertEquals(READ_UNAVAILABLE, missing.status()); assertNull(missing.view());
  }

  @Test void revokedStaleAndNoLiveIdentityStillDenyBeforeLookupAfterWithdrawal() throws Exception {
    withdraw();
    for (Gate gate : Gate.values()) for (State state : List.of(State.REVOKED, State.STALE, State.UNKNOWN)) {
      var c = coach(); var p = c.evidence.get(gate);
      var invalid = proof(c, gate, new Evidence(p.gate(), p.principal(), p.tenant(), p.subject(), p.resource(), p.purpose(), p.operation(), p.policyRef(), p.decisionRef(), 1, state, p.effectiveAt(), p.expiresAt(), null));
      assertGuardDeniesBeforeLookup(invalid, request(invalid));
    }
    byte[] before = Files.readAllBytes(path);
    for (var source : List.of(journal, JourneyJournal.open(path))) {
      AtomicInteger calls = new AtomicInteger();
      var repository = new ClientRelationshipRepository(id -> { calls.incrementAndGet(); return snapshot(source, id); });
      var result = new ArcavaAccessService(new OwnerGuard(CLOCK), repository).readEnrollment(request(coach()));
      assertEquals(ACCESS_DENIED, result.status()); assertNull(result.view()); assertEquals(0, calls.get());
    }
    assertArrayEquals(before, Files.readAllBytes(path));
  }

  @Test void readWaitsForJournalMonitorAndSeesCommittedWithdrawalWithoutSleeps() throws Exception {
    var c = coach();
    var access = service(c, new ClientRelationshipRepository(journal));
    CompletableFuture<Result> completed = new CompletableFuture<>();
    CountDownLatch started = new CountDownLatch(1);
    Thread reader = Thread.ofPlatform().unstarted(() -> {
      started.countDown();
      try { completed.complete(access.readEnrollment(request(c))); }
      catch (Throwable failure) { completed.completeExceptionally(failure); }
    });
    try {
      synchronized (journal) {
        reader.start();
        assertTrue(started.await(5, TimeUnit.SECONDS));
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (reader.getState() != Thread.State.BLOCKED && !completed.isDone() && System.nanoTime() < deadline)
          Thread.onSpinWait();
        assertEquals(Thread.State.BLOCKED, reader.getState(), "reader must use the withdrawal monitor");
        assertFalse(completed.isDone());
        withdraw(); // reentrant monitor; commits before reader may snapshot
      }
      Result result = completed.get(5, TimeUnit.SECONDS);
      assertEquals(NOT_FOUND, result.status()); assertNull(result.view());
      assertBeforeAndAfterReplay(c, NOT_FOUND);
    } finally {
      reader.join(5000);
      assertFalse(reader.isAlive());
    }
  }

  @Test void actualAssignmentSnapshotMatchesEnrollmentForBothRolesAfterReplay() throws Exception {
    byte[] before = Files.readAllBytes(path);
    UUID assignmentId = UUID.fromString(link.assignmentId());
    var expected = new AssignmentView(TENANT.toString(), assignmentId, CLIENT.toString(), UUID.fromString(link.versionId()), "active");
    for (var source : List.of(journal, JourneyJournal.open(path))) {
      assertEquals(expected, source.assignmentSnapshot(assignmentId));
      assertEquals(expected, source.kernel().assignmentSnapshot(assignmentId));
      assertNull(source.assignmentSnapshot(OTHER));
      assertNull(source.assignmentSnapshot(null));
      for (Role role : List.of(Role.COACH, Role.CLIENT))
        assertEquals(ALLOWED, read(synthetic(role, TENANT, CLIENT, enrollment), source).status());
    }
    assertArrayEquals(before, Files.readAllBytes(path));
  }

  @Test void missingForeignChangedAndInactiveAssignmentSnapshotsDenyAfterReplay() throws Exception {
    byte[] before = Files.readAllBytes(path);
    for (var source : List.of(journal, JourneyJournal.open(path))) {
      var real = snapshot(source, enrollment);
      AssignmentView a = real.assignment();
      List<AssignmentView> invalid = new ArrayList<>();
      invalid.add(null);
      for (String value : Arrays.asList(null, "", "private-malformed-id", "1-1-1-1-1", OTHER.toString(), new UUID(0, 0).toString())) {
        invalid.add(new AssignmentView(value, a.assignmentId(), a.clientId(), a.journeyVersionId(), "active"));
        invalid.add(new AssignmentView(a.tenantId(), a.assignmentId(), value, a.journeyVersionId(), "active"));
      }
      for (UUID value : Arrays.asList(null, OTHER, new UUID(0, 0))) {
        invalid.add(new AssignmentView(a.tenantId(), value, a.clientId(), a.journeyVersionId(), "active"));
        invalid.add(new AssignmentView(a.tenantId(), a.assignmentId(), a.clientId(), value, "active"));
      }
      // SYNTHETIC_TEST_ONLY storage corruption: source has no assignment-revoke API.
      for (String status : Arrays.asList(null, "", "UNKNOWN", "revoked", "inactive", "ACTIVE", "private-status"))
        invalid.add(new AssignmentView(a.tenantId(), a.assignmentId(), a.clientId(), a.journeyVersionId(), status));
      for (Role role : List.of(Role.COACH, Role.CLIENT)) {
        var c = synthetic(role, TENANT, CLIENT, enrollment);
        for (AssignmentView bad : invalid) {
          var repository = new ClientRelationshipRepository(id -> new EnrollmentSnapshot(real.enrollment(), real.projection(), bad));
          var result = service(c, repository).readEnrollment(request(c));
          assertEquals(NOT_FOUND, result.status()); assertNull(result.view());
          assertFalse(result.toString().contains("private"));
        }
        // A valid-shaped but changed enrollment assignment reference cannot resolve to the old record.
        var changed = new EnrollmentLink(link.tenantId(), link.clientId(), link.versionId(), OTHER.toString(), link.enrollmentId());
        var repository = new ClientRelationshipRepository(id -> new EnrollmentSnapshot(changed, real.projection(), a));
        assertEquals(NOT_FOUND, service(c, repository).readEnrollment(request(c)).status());
      }
    }
    assertArrayEquals(before, Files.readAllBytes(path));
  }

  @Test void assignmentLinkageCannotBypassGuardOrPublicationWithdrawal() throws Exception {
    withdraw();
    byte[] before = Files.readAllBytes(path);
    for (var source : List.of(journal, JourneyJournal.open(path))) {
      var real = snapshot(source, enrollment);
      assertEquals("active", real.assignment().status(), "withdrawal does not revoke the local assignment");
      for (Role role : List.of(Role.COACH, Role.CLIENT)) {
        var c = synthetic(role, TENANT, CLIENT, enrollment);
        assertEquals(NOT_FOUND, read(c, source).status(), "active assignment cannot defeat withdrawn projection");
      }
      for (Role role : List.of(Role.TENANT_ADMIN, Role.ARCAVA_APPLICATION_SERVICE)) {
        var c = synthetic(role, TENANT, CLIENT, enrollment);
        assertGuardDeniesBeforeLookup(c, request(c));
      }
      AtomicInteger calls = new AtomicInteger();
      var unavailable = new ClientRelationshipRepository(id -> { calls.incrementAndGet(); throw new IllegalStateException("private-assignment-source"); });
      var result = service(coach(), unavailable).readEnrollment(request(coach()));
      assertEquals(READ_UNAVAILABLE, result.status()); assertNull(result.view());
      assertEquals(1, calls.get()); assertFalse(result.toString().contains("private"));
      var c = proof(coach(), Gate.ASSIGNMENT, null);
      calls.set(0);
      assertEquals(ACCESS_DENIED, service(c, unavailable).readEnrollment(request(c)).status());
      assertEquals(0, calls.get());
    }
    assertArrayEquals(before, Files.readAllBytes(path));
  }

  @Test void publishedJournalIdentityMapsExactlyAfterGuardedReadAndReplay() throws Exception {
    byte[] before = Files.readAllBytes(path);
    var expected = ClientRelationshipModel.from(link).typedIdentity();
    for (var source : List.of(journal, JourneyJournal.open(path))) for (Role role : List.of(Role.COACH, Role.CLIENT)) {
      var c = synthetic(role, TENANT, CLIENT, enrollment);
      var repository = new ClientRelationshipRepository(source);
      var result = service(c, repository).readEnrollment(request(c));
      assertEquals(ALLOWED, result.status());
      var stored = repository.enrollment(enrollment);
      assertEquals(ClientRelationshipRepository.Status.FOUND, stored.status());
      var typed = stored.model().typedIdentity();
      assertDoesNotThrow(() -> typed.requireSameIdentity(expected));
      assertEquals(result.view().enrollmentId(), typed.enrollmentId().value());
      assertEquals(result.view().journeyVersionId(), typed.versionId().value());
      assertEquals(UUID.fromString(link.assignmentId()), typed.assignmentId().value());
      assertEquals(TENANT, typed.tenantId().value()); assertEquals(CLIENT, typed.clientId().value());
    }
    assertArrayEquals(before, Files.readAllBytes(path));
  }

  @Test void typedReferencesCannotAdmitMismatchedWithdrawnOrUntrustedJournalRead() throws Exception {
    byte[] before = Files.readAllBytes(path);
    // SYNTHETIC_TEST_ONLY storage fault seam; a typed identity is not a current linkage proof.
    for (var source : List.of(journal, JourneyJournal.open(path))) {
      var real = snapshot(source, enrollment);
      var a = real.assignment();
      var wrong = new AssignmentView(a.tenantId(), OTHER, a.clientId(), a.journeyVersionId(), a.status());
      var repository = new ClientRelationshipRepository(id -> new EnrollmentSnapshot(real.enrollment(), real.projection(), wrong));
      var result = service(coach(), repository).readEnrollment(request(coach()));
      assertEquals(NOT_FOUND, result.status()); assertNull(result.view());
      assertNull(repository.enrollment(enrollment).model(), "no identity bridge payload from failed linkage");
    }
    assertArrayEquals(before, Files.readAllBytes(path));
    var priorTyped = ClientRelationshipModel.from(link).typedIdentity();
    withdraw();
    byte[] withdrawn = Files.readAllBytes(path);
    for (var source : List.of(journal, JourneyJournal.open(path))) {
      var repository = new ClientRelationshipRepository(source);
      assertEquals(NOT_FOUND, read(coach(), source).status());
      assertNull(repository.enrollment(priorTyped.enrollmentId().value()).model());
      AtomicInteger calls = new AtomicInteger();
      var counted = new ClientRelationshipRepository(id -> { calls.incrementAndGet(); return snapshot(source, id); });
      var result = new ArcavaAccessService(new OwnerGuard(CLOCK), counted).readEnrollment(request(coach()));
      assertEquals(ACCESS_DENIED, result.status()); assertNull(result.view()); assertEquals(0, calls.get());
      assertFalse(result.toString().contains(link.assignmentId()));
    }
    assertArrayEquals(withdrawn, Files.readAllBytes(path));
  }
}
