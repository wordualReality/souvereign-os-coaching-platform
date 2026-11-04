package com.projectb.api.arcava.security;

import com.projectb.api.arcava.repositories.ClientRelationshipRepository;
import com.projectb.api.arcava.services.ArcavaAccessService;
import com.projectb.api.arcava.services.ArcavaAccessService.Result;
import com.projectb.api.domain.JourneyJournal;
import com.projectb.api.domain.JourneyJournal.EnrollmentLink;
import com.projectb.api.domain.JourneyKernel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
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
        calls.incrementAndGet(); return source.enrollment(id);
      });
      var result = service(c, repository).readEnrollment(request);
      assertEquals(ACCESS_DENIED, result.status()); assertNull(result.view());
      assertEquals(0, calls.get(), "guard must precede storage/existence lookup");
      assertFalse(result.toString().contains("synthetic-policy"));
    }
    assertArrayEquals(before, Files.readAllBytes(path));
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
    var result = service(coach(), new ClientRelationshipRepository(id -> swapped)).readEnrollment(request(coach()));
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
    var repository = new ClientRelationshipRepository(id -> { calls.incrementAndGet(); return link; });
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
      var result = service(coach(), new ClientRelationshipRepository(id -> malformed)).readEnrollment(request(coach()));
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
}
