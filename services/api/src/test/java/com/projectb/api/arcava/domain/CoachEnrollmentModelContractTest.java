package com.projectb.api.arcava.domain;

import com.projectb.api.arcava.security.OwnerGuard;
import com.projectb.api.arcava.security.TrustedRequestContext.*;
import java.time.*;
import java.util.*;
import java.util.function.Function;
import org.junit.jupiter.api.Test;
import static com.projectb.api.arcava.domain.CoachEnrollmentModel.*;
import static com.projectb.api.arcava.domain.TenantModel.*;
import static org.junit.jupiter.api.Assertions.*;

/** SYNTHETIC_TEST_ONLY snapshots. No external issuer, role or activation attestation. */
class CoachEnrollmentModelContractTest {
  static final Instant NOW = Instant.parse("2026-11-05T12:00:00Z");
  static final TenantId TENANT = new TenantId(new UUID(0, 2));
  static final ClientId CLIENT = new ClientId(new UUID(0, 3));
  static final PiacPrincipalRef COACH = new PiacPrincipalRef(new UUID(0, 4));
  static final AssignmentId ASSIGNMENT = new AssignmentId(new UUID(0, 6));
  static final EnrollmentId ENROLLMENT = new EnrollmentId(new UUID(0, 7));
  static final JourneyVersionRef VERSION = new JourneyVersionRef(new UUID(0, 8));
  static final UUID OTHER = new UUID(0, 99);

  static CoachAssignment assignment(AssignmentState state, Instant from, Optional<Instant> until) {
    return new CoachAssignment(ASSIGNMENT, TENANT, CLIENT, COACH, RoleKnowledge.UNKNOWN, state, from, until);
  }
  static Enrollment enrollment(EnrollmentState state) { return new Enrollment(ENROLLMENT, TENANT, CLIENT, VERSION, state, NOW); }
  static ClientProfile client(TenantId tenant, ClientId client) {
    return new ClientProfile(client, tenant, Optional.empty(), UnresolvedLifecycle.UNKNOWN, Optional.empty());
  }

  @Test void typedCanonicalSnapshotsPreserveDistinctNamespacesAndClientScope() {
    var a = assignment(AssignmentState.PENDING, NOW, Optional.empty());
    var e = enrollment(EnrollmentState.PENDING);
    assertEquals(ASSIGNMENT, AssignmentId.parse(ASSIGNMENT.value().toString()));
    assertEquals(ENROLLMENT, EnrollmentId.parse(ENROLLMENT.value().toString()));
    assertEquals(VERSION, JourneyVersionRef.parse(VERSION.value().toString()));
    assertEquals(Namespace.ARCAVA, a.id().namespace()); assertEquals(Namespace.PIAC, a.coachPrincipalRef().namespace());
    assertEquals(Namespace.ARCAVA, e.id().namespace()); assertEquals(Namespace.ARCAVA, e.journeyVersionRef().namespace());
    assertNotEquals(new AssignmentId(OTHER), new EnrollmentId(OTHER));
    assertNotEquals(new EnrollmentId(OTHER), new JourneyVersionRef(OTHER));
    assertNotEquals(new JourneyVersionRef(OTHER), new PiacPrincipalRef(OTHER));
    assertDoesNotThrow(() -> a.requireClient(client(TENANT, CLIENT)));
    assertDoesNotThrow(() -> e.requireClient(client(TENANT, CLIENT)));
    assertEquals(RoleKnowledge.UNKNOWN, a.role()); assertEquals(Verification.NOT_VERIFIED, a.verification());
  }

  @Test void stateLabelsMatchExactSmArc02And03WithoutNewRoleStates() {
    assertEquals(List.of("PENDING", "ACTIVE", "ENDED", "REVOKED"), Arrays.stream(AssignmentState.values()).map(Enum::name).toList());
    assertEquals(List.of("PENDING", "ACTIVE", "COMPLETED", "CANCELLED", "REVOKED"), Arrays.stream(EnrollmentState.values()).map(Enum::name).toList());
    assertThrows(IllegalArgumentException.class, () -> AssignmentState.valueOf("UNKNOWN"));
    assertThrows(IllegalArgumentException.class, () -> EnrollmentState.valueOf("active"));
    assertEquals(List.of("UNKNOWN", "NOT_VERIFIED"), Arrays.stream(RoleKnowledge.values()).map(Enum::name).toList());
  }

  @Test void malformedNilAndForeignFormatIdsRejectWithoutRawDiagnostics() {
    List<Function<String, ?>> parsers = List.of(AssignmentId::parse, EnrollmentId::parse, JourneyVersionRef::parse);
    for (var parser : parsers) for (String invalid : Arrays.asList(null, "", "private-invalid-id", "1-1-1-1-1", "PIAC:" + OTHER, "KDB:" + OTHER, new UUID(0, 0).toString(), OTHER + " ", "ABCDEF00-0000-0000-0000-000000000001")) {
      var error = assertThrows(IllegalArgumentException.class, () -> parser.apply(invalid));
      assertFalse(error.getMessage().contains("private")); assertNull(error.getCause());
    }
    for (UUID invalid : Arrays.asList(null, new UUID(0, 0))) {
      assertThrows(IllegalArgumentException.class, () -> new AssignmentId(invalid));
      assertThrows(IllegalArgumentException.class, () -> new EnrollmentId(invalid));
      assertThrows(IllegalArgumentException.class, () -> new JourneyVersionRef(invalid));
    }
  }

  @Test void wrongTenantClientAndMissingOwnerLinksFailClosed() {
    var a = assignment(AssignmentState.ACTIVE, NOW, Optional.empty()); var e = enrollment(EnrollmentState.ACTIVE);
    for (var profile : List.of(client(new TenantId(OTHER), CLIENT), client(TENANT, new ClientId(OTHER)))) {
      assertThrows(IllegalArgumentException.class, () -> a.requireClient(profile));
      assertThrows(IllegalArgumentException.class, () -> e.requireClient(profile));
    }
    assertThrows(IllegalArgumentException.class, () -> a.requireClient(null));
    assertThrows(IllegalArgumentException.class, () -> e.requireClient(null));
    assertThrows(IllegalArgumentException.class, () -> a.requireScope(null, CLIENT));
    assertThrows(IllegalArgumentException.class, () -> e.requireScope(TENANT, null));
  }

  @Test void everyRequiredIdentityStatusRoleAndTimeRejectsNull() {
    Object[] values = {ASSIGNMENT, TENANT, CLIENT, COACH, RoleKnowledge.UNKNOWN, AssignmentState.PENDING, NOW, Optional.empty()};
    for (int i = 0; i < values.length; i++) {
      Object[] bad = values.clone(); bad[i] = null;
      assertThrows(IllegalArgumentException.class, () -> constructAssignment(bad));
    }
    Object[] enrolled = {ENROLLMENT, TENANT, CLIENT, VERSION, EnrollmentState.PENDING, NOW};
    for (int i = 0; i < enrolled.length; i++) {
      Object[] bad = enrolled.clone(); bad[i] = null;
      assertThrows(IllegalArgumentException.class, () -> new Enrollment((EnrollmentId)bad[0], (TenantId)bad[1], (ClientId)bad[2], (JourneyVersionRef)bad[3], (EnrollmentState)bad[4], (Instant)bad[5]));
    }
  }
  @SuppressWarnings("unchecked") static CoachAssignment constructAssignment(Object[] v) {
    return new CoachAssignment((AssignmentId)v[0], (TenantId)v[1], (ClientId)v[2], (PiacPrincipalRef)v[3], (RoleKnowledge)v[4], (AssignmentState)v[5], (Instant)v[6], (Optional<Instant>)v[7]);
  }

  @Test void temporalWindowBoundariesAreExplicitAndNeverGrantAuthority() {
    assertThrows(IllegalArgumentException.class, () -> assignment(AssignmentState.ACTIVE, NOW, Optional.of(NOW.minusSeconds(1))));
    assertThrows(IllegalArgumentException.class, () -> assignment(AssignmentState.ACTIVE, NOW, Optional.of(NOW)));
    var a = assignment(AssignmentState.ACTIVE, NOW, Optional.of(NOW.plusSeconds(10)));
    assertDoesNotThrow(() -> a.requireCurrentWindow(NOW));
    assertDoesNotThrow(() -> a.requireCurrentWindow(NOW.plusSeconds(9)));
    assertThrows(IllegalArgumentException.class, () -> a.requireCurrentWindow(NOW.minusNanos(1)));
    assertThrows(IllegalArgumentException.class, () -> a.requireCurrentWindow(NOW.plusSeconds(10)));
    assertThrows(IllegalArgumentException.class, () -> a.requireCurrentWindow(null));
    var open = assignment(AssignmentState.PENDING, NOW, Optional.empty());
    assertDoesNotThrow(() -> open.requireCurrentWindow(NOW.plusSeconds(100)));
    assertEquals(AssignmentState.PENDING, open.status()); assertEquals(Verification.NOT_VERIFIED, open.verification());
  }

  @Test void activeLabelsMissingOrExpiredTrustNeverOpenProductionOwnerGuard() {
    var guard = new OwnerGuard(Clock.fixed(NOW, ZoneOffset.UTC));
    for (AssignmentState state : AssignmentState.values()) for (EnrollmentState enrolled : EnrollmentState.values()) {
      var a = assignment(state, NOW.minusSeconds(60), Optional.of(NOW.minusSeconds(1))); // historical expired snapshot
      var e = enrollment(enrolled);
      assertEquals(Verification.NOT_VERIFIED, a.verification()); assertEquals(Verification.NOT_VERIFIED, e.verification());
      assertThrows(IllegalArgumentException.class, () -> a.requireCurrentWindow(NOW));
      var request = new Request(a.coachPrincipalRef().value(), a.tenantId().value(), a.clientId().value(), e.id().value(), Purpose.COACHING_SUPPORT, Operation.SENSITIVE_CLIENT_READ, 1);
      var denied = guard.authorize(request);
      assertFalse(denied.allowed()); assertEquals(OwnerGuard.Reason.PIAC_NOT_CONNECTED, denied.reason()); assertTrue(denied.decisionReferences().isEmpty());
    }
    var a = assignment(AssignmentState.ACTIVE, NOW, Optional.empty());
    assertDoesNotThrow(() -> a.requireCurrentWindow(NOW));
    assertFalse(guard.authorize(new Request(COACH.value(), TENANT.value(), CLIENT.value(), ENROLLMENT.value(), Purpose.COACHING_SUPPORT, Operation.SENSITIVE_CLIENT_READ, 1)).allowed());
  }

  @Test void snapshotsAndDiagnosticStringsDoNotLeakPrincipalOrCarryMutableLifecycle() {
    Optional<Instant> until = Optional.of(NOW.plusSeconds(10));
    var a = assignment(AssignmentState.PENDING, NOW, until);
    until = Optional.of(NOW.plusSeconds(20));
    assertEquals(NOW.plusSeconds(10), a.validUntil().orElseThrow());
    assertEquals(AssignmentState.PENDING, a.status());
    var e = enrollment(EnrollmentState.PENDING);
    assertEquals(NOW, e.effectiveAt()); assertEquals(VERSION, e.journeyVersionRef());
    for (Object value : List.of(a, e)) {
      assertFalse(value.toString().contains(COACH.value().toString()));
      assertFalse(value.toString().contains(CLIENT.value().toString()));
    }
  }
}
