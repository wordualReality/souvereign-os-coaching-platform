package com.projectb.api.arcava.domain;

import com.projectb.api.domain.JourneyJournal.EnrollmentLink;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static com.projectb.api.arcava.domain.TenantModel.*;
import static com.projectb.api.arcava.domain.CoachEnrollmentModel.*;
import com.projectb.api.arcava.domain.ClientRelationshipModel.JournalIdentity;

/** SYNTHETIC_TEST_ONLY pure mapping; never proof of current linkage, lifecycle or permission. */
class JournalIdentityBindingContractTest {
  static final UUID TENANT = new UUID(0, 2), CLIENT = new UUID(0, 3), VERSION = new UUID(0, 8),
      ASSIGNMENT = new UUID(0, 6), ENROLLMENT = new UUID(0, 7), OTHER = new UUID(0, 99);
  static ClientRelationshipModel source() { return new ClientRelationshipModel(TENANT, CLIENT, VERSION, ASSIGNMENT, ENROLLMENT); }

  @Test void mapsExactFiveExistingFieldsInSourceOrderWithoutInventedAggregateData() {
    var typed = source().typedIdentity();
    assertEquals(new TenantId(TENANT), typed.tenantId()); assertEquals(new ClientId(CLIENT), typed.clientId());
    assertEquals(new JourneyVersionRef(VERSION), typed.versionId()); assertEquals(new AssignmentId(ASSIGNMENT), typed.assignmentId());
    assertEquals(new EnrollmentId(ENROLLMENT), typed.enrollmentId());
    assertEquals(typed, ClientRelationshipModel.from(new EnrollmentLink(TENANT.toString(), CLIENT.toString(), VERSION.toString(), ASSIGNMENT.toString(), ENROLLMENT.toString())).typedIdentity());
    assertDoesNotThrow(() -> typed.requireScope(new TenantId(TENANT), new ClientId(CLIENT)));
    assertDoesNotThrow(() -> typed.requireSameIdentity(source().typedIdentity()));
  }

  @Test void equalUuidBytesRemainDifferentTypedObjectAndOwnerNamespaces() {
    var typed = new ClientRelationshipModel(OTHER, OTHER, OTHER, OTHER, OTHER).typedIdentity();
    assertNotEquals(typed.tenantId(), typed.clientId()); assertNotEquals(typed.assignmentId(), typed.enrollmentId());
    assertNotEquals(typed.versionId(), typed.enrollmentId());
    assertNotEquals(typed.clientId(), new PiacPrincipalRef(OTHER));
    assertEquals(Namespace.ARCAVA, typed.versionId().namespace());
    assertEquals(Namespace.PIAC, new PiacPrincipalRef(OTHER).namespace());
  }

  @Test void invalidNullAndNilSourceValuesNeverProduceTypedIdentity() {
    UUID[] valid = {TENANT, CLIENT, VERSION, ASSIGNMENT, ENROLLMENT};
    for (int field = 0; field < 5; field++) for (UUID invalid : Arrays.asList(null, new UUID(0, 0))) {
      UUID[] bad = valid.clone(); bad[field] = invalid;
      assertThrows(RuntimeException.class, () -> new ClientRelationshipModel(bad[0], bad[1], bad[2], bad[3], bad[4]).typedIdentity());
    }
    for (int field = 0; field < 5; field++) for (String invalid : Arrays.asList(null, "private-invalid-id", "1-1-1-1-1", "PIAC:" + OTHER)) {
      String[] bad = Arrays.stream(valid).map(UUID::toString).toArray(String[]::new); bad[field] = invalid;
      assertThrows(RuntimeException.class, () -> ClientRelationshipModel.from(new EnrollmentLink(bad[0], bad[1], bad[2], bad[3], bad[4])).typedIdentity());
    }
    var t = source().typedIdentity();
    assertThrows(IllegalArgumentException.class, () -> new JournalIdentity(null, t.clientId(), t.versionId(), t.assignmentId(), t.enrollmentId()));
    assertThrows(IllegalArgumentException.class, () -> new JournalIdentity(t.tenantId(), null, t.versionId(), t.assignmentId(), t.enrollmentId()));
    assertThrows(IllegalArgumentException.class, () -> new JournalIdentity(t.tenantId(), t.clientId(), null, t.assignmentId(), t.enrollmentId()));
    assertThrows(IllegalArgumentException.class, () -> new JournalIdentity(t.tenantId(), t.clientId(), t.versionId(), null, t.enrollmentId()));
    assertThrows(IllegalArgumentException.class, () -> new JournalIdentity(t.tenantId(), t.clientId(), t.versionId(), t.assignmentId(), null));
  }

  @Test void eachWrongTenantClientVersionAssignmentAndEnrollmentFailsExactComparison() {
    var t = source().typedIdentity();
    UUID[] valid = {TENANT, CLIENT, VERSION, ASSIGNMENT, ENROLLMENT};
    for (int field = 0; field < 5; field++) {
      UUID[] bad = valid.clone(); bad[field] = OTHER;
      var changed = new ClientRelationshipModel(bad[0], bad[1], bad[2], bad[3], bad[4]).typedIdentity();
      var error = assertThrows(IllegalArgumentException.class, () -> t.requireSameIdentity(changed));
      assertFalse(error.getMessage().contains(OTHER.toString()));
    }
    assertThrows(IllegalArgumentException.class, () -> t.requireSameIdentity(null));
    assertThrows(IllegalArgumentException.class, () -> t.requireScope(new TenantId(OTHER), t.clientId()));
    assertThrows(IllegalArgumentException.class, () -> t.requireScope(t.tenantId(), new ClientId(OTHER)));
    assertThrows(IllegalArgumentException.class, () -> t.requireScope(null, t.clientId()));
  }

  @Test void immutablePureProjectionRedactsDiagnosticReferences() {
    var model = source(); var t = model.typedIdentity();
    assertEquals(t, model.typedIdentity()); assertEquals(VERSION, model.versionId());
    for (UUID id : List.of(TENANT, CLIENT, VERSION, ASSIGNMENT, ENROLLMENT)) assertFalse(t.toString().contains(id.toString()));
  }
}
