package com.projectb.api.arcava.domain;

import com.projectb.api.arcava.security.OwnerGuard;
import com.projectb.api.arcava.security.TrustedRequestContext.*;
import java.math.BigInteger;
import java.time.*;
import java.util.*;
import java.util.function.Function;
import org.junit.jupiter.api.Test;
import static com.projectb.api.arcava.domain.TenantModel.*;
import static org.junit.jupiter.api.Assertions.*;

/** SYNTHETIC_TEST_ONLY model snapshots, not admitted PIAC identity or tenant activation. */
class TenantModelContractTest {
  static final UUID TENANT = new UUID(0, 2), CLIENT = new UUID(0, 3), PRINCIPAL = new UUID(0, 4),
      MEMBERSHIP = new UUID(0, 5), OTHER = new UUID(0, 99);
  static final Instant NOW = Instant.parse("2026-11-04T12:00:00Z");
  static final TenantId T = new TenantId(TENANT);
  static final ClientId C = new ClientId(CLIENT);
  static final PiacPrincipalRef P = new PiacPrincipalRef(PRINCIPAL);

  static ClientProfile client(UnresolvedLifecycle status) {
    return new ClientProfile(C, T, Optional.of(P), status, Optional.of(new SensitiveProfileRef("private-profile-ref")));
  }
  static TenantMembership membership(Optional<BigInteger> revision, UnresolvedLifecycle status) {
    return new TenantMembership(new MembershipId(MEMBERSHIP), T, P, NOW, revision, status);
  }

  @Test void canonicalTenantClientAndExternalPrincipalAreDistinctTypedSnapshots() {
    var tenant = new BusinessTenant(TenantId.parse(TENANT.toString()), "synthetic tenant", Optional.of(TenantState.PROVISIONING), Optional.empty(), Optional.empty());
    var profile = client(UnresolvedLifecycle.UNKNOWN);
    assertEquals(T, tenant.id()); assertEquals(C, profile.id());
    assertEquals(Namespace.ARCAVA, profile.id().namespace());
    assertEquals(Namespace.PIAC, profile.principalRef().orElseThrow().namespace());
    assertDoesNotThrow(() -> profile.requireScope(tenant.id(), C));
    assertNotEquals(new TenantId(TENANT), new ClientId(TENANT));
    assertNotEquals(new ClientId(PRINCIPAL), new PiacPrincipalRef(PRINCIPAL));
    assertNotEquals(new MembershipId(TENANT), new TenantId(TENANT));
  }

  @Test void optionalReferencesDoNotMaterializeOrEquateExternalIdentity() {
    var tenant = new BusinessTenant(T, "synthetic", Optional.empty(), Optional.of(new ArcavaConfigRef(OTHER)), Optional.of("legal-ref"));
    var unlinked = new ClientProfile(C, T, Optional.empty(), UnresolvedLifecycle.NOT_VERIFIED, Optional.empty());
    assertTrue(tenant.status().isEmpty()); assertTrue(unlinked.principalRef().isEmpty());
    assertTrue(unlinked.privateProfileRef().isEmpty());
    assertEquals(Verification.NOT_VERIFIED, unlinked.verification());
    assertEquals(UnresolvedLifecycle.UNKNOWN, tenant.unresolvedStatus().orElseThrow());
    assertEquals(Namespace.ARCAVA, tenant.brandingConfigRef().orElseThrow().namespace());
  }

  @Test void recordsAndOptionalValuesRemainImmutableSnapshots() {
    Optional<TenantState> state = Optional.of(TenantState.PROVISIONING);
    var tenant = new BusinessTenant(T, "synthetic", state, Optional.empty(), Optional.empty());
    state = Optional.of(TenantState.ACTIVE);
    assertEquals(TenantState.PROVISIONING, tenant.status().orElseThrow());
    var member = membership(Optional.of(BigInteger.ONE), UnresolvedLifecycle.UNKNOWN);
    assertEquals(NOW, member.createdAt()); assertEquals(BigInteger.ONE, member.revision().orElseThrow());
    assertEquals(Verification.NOT_VERIFIED, member.verification());
  }

  @Test void malformedNilAndForeignNamespaceStringsAreRejectedWithoutEcho() {
    List<Function<String, ?>> parsers = List.of(TenantId::parse, ClientId::parse, MembershipId::parse, PiacPrincipalRef::parse);
    for (var parser : parsers) for (String invalid : Arrays.asList(null, "", "private-malformed-id", "1-1-1-1-1", "KDB:" + TENANT, "PIAC:" + TENANT, new UUID(0, 0).toString(), TENANT + " ", "ABCDEF00-0000-0000-0000-000000000001")) {
      var error = assertThrows(IllegalArgumentException.class, () -> parser.apply(invalid));
      assertFalse(error.getMessage().contains("private")); assertNull(error.getCause());
    }
    assertThrows(IllegalArgumentException.class, () -> new TenantId(null));
    assertThrows(IllegalArgumentException.class, () -> new ClientId(new UUID(0, 0)));
    assertThrows(IllegalArgumentException.class, () -> new MembershipId(new UUID(0, 0)));
    assertThrows(IllegalArgumentException.class, () -> new PiacPrincipalRef(new UUID(0, 0)));
    assertThrows(IllegalArgumentException.class, () -> new ArcavaConfigRef(new UUID(0, 0)));
  }

  @Test void wrongTenantAndClientNeverMatchLocalScope() {
    var profile = client(UnresolvedLifecycle.UNKNOWN);
    assertThrows(IllegalArgumentException.class, () -> profile.requireScope(new TenantId(OTHER), C));
    assertThrows(IllegalArgumentException.class, () -> profile.requireScope(T, new ClientId(OTHER)));
    assertThrows(IllegalArgumentException.class, () -> profile.requireScope(null, C));
    var member = membership(Optional.empty(), UnresolvedLifecycle.UNKNOWN);
    assertDoesNotThrow(() -> member.requireTenant(T));
    assertThrows(IllegalArgumentException.class, () -> member.requireTenant(new TenantId(OTHER)));
    assertThrows(IllegalArgumentException.class, () -> member.requireTenant(null));
  }

  @Test void requiredProvenanceAndUnknownStatusCannotDefaultToActive() {
    assertThrows(IllegalArgumentException.class, () -> new BusinessTenant(T, "synthetic", null, Optional.empty(), Optional.empty()));
    assertThrows(IllegalArgumentException.class, () -> client(null));
    assertThrows(IllegalArgumentException.class, () -> membership(Optional.empty(), null));
    assertThrows(IllegalArgumentException.class, () -> new TenantMembership(new MembershipId(MEMBERSHIP), T, P, null, Optional.empty(), UnresolvedLifecycle.UNKNOWN));
    assertThrows(IllegalArgumentException.class, () -> new TenantMembership(new MembershipId(MEMBERSHIP), T, null, NOW, Optional.empty(), UnresolvedLifecycle.UNKNOWN));
    assertThrows(IllegalArgumentException.class, () -> new ClientProfile(C, null, Optional.empty(), UnresolvedLifecycle.UNKNOWN, Optional.empty()));
    assertThrows(IllegalArgumentException.class, () -> new BusinessTenant(T, " ", Optional.empty(), Optional.empty(), Optional.empty()));
    assertThrows(IllegalArgumentException.class, () -> new BusinessTenant(T, "synthetic", Optional.empty(), Optional.empty(), Optional.of(" ")));
    assertThrows(IllegalArgumentException.class, () -> new SensitiveProfileRef(" "));
  }

  @Test void membershipRevisionUsesOnlyExplicitUnsignedSourceValue() {
    assertTrue(membership(Optional.empty(), UnresolvedLifecycle.UNKNOWN).revision().isEmpty());
    assertEquals(BigInteger.ZERO, membership(Optional.of(BigInteger.ZERO), UnresolvedLifecycle.UNKNOWN).revision().orElseThrow());
    var max = BigInteger.ONE.shiftLeft(64).subtract(BigInteger.ONE);
    assertEquals(max, membership(Optional.of(max), UnresolvedLifecycle.NOT_VERIFIED).revision().orElseThrow());
    assertThrows(IllegalArgumentException.class, () -> membership(Optional.of(BigInteger.valueOf(-1)), UnresolvedLifecycle.UNKNOWN));
    assertThrows(IllegalArgumentException.class, () -> membership(Optional.of(BigInteger.ONE.shiftLeft(64)), UnresolvedLifecycle.UNKNOWN));
  }

  @Test void activeTenantAndMembershipNeverAuthorizeSensitiveReadWithoutLiveProof() {
    for (TenantState state : TenantState.values()) for (UnresolvedLifecycle unknown : UnresolvedLifecycle.values()) {
      var tenant = new BusinessTenant(T, "synthetic", Optional.of(state), Optional.empty(), Optional.empty());
      var profile = client(unknown); var member = membership(Optional.of(BigInteger.ONE), unknown);
      assertEquals(Verification.NOT_VERIFIED, tenant.verification());
      assertTrue(tenant.unresolvedStatus().isEmpty());
      assertEquals(Verification.NOT_VERIFIED, profile.verification());
      assertEquals(Verification.NOT_VERIFIED, member.verification());
      var guard = new OwnerGuard(Clock.fixed(NOW, ZoneOffset.UTC));
      var request = new Request(member.principalRef().value(), tenant.id().value(), profile.id().value(), OTHER, Purpose.COACHING_SUPPORT, Operation.SENSITIVE_CLIENT_READ, 1);
      var decision = guard.authorize(request);
      assertFalse(decision.allowed()); assertEquals(OwnerGuard.Reason.PIAC_NOT_CONNECTED, decision.reason());
      assertTrue(decision.decisionReferences().isEmpty());
    }
  }

  @Test void privateReferencesAndLabelsAreAbsentFromDiagnosticStrings() {
    var tenant = new BusinessTenant(T, "private-tenant-name", Optional.of(TenantState.ACTIVE), Optional.empty(), Optional.of("private-legal-ref"));
    var profile = client(UnresolvedLifecycle.NOT_VERIFIED);
    var member = membership(Optional.empty(), UnresolvedLifecycle.UNKNOWN);
    for (Object value : List.of(tenant, profile, member, P, profile.privateProfileRef().orElseThrow())) {
      assertFalse(value.toString().contains("private"));
      assertFalse(value.toString().contains(PRINCIPAL.toString()));
    }
  }
}
