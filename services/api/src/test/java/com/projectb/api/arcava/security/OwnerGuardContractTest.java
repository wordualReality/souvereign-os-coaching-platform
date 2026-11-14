package com.projectb.api.arcava.security;

import com.projectb.api.arcava.services.CoachClientAccessService;
import com.projectb.api.http.TrustedPiacVerifier;
import com.projectb.api.http.TrustedKdbVerifier;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static com.projectb.api.arcava.security.TrustedRequestContext.*;
import static com.projectb.api.arcava.security.OwnerGuard.Reason.*;

class OwnerGuardContractTest {
  static final Instant NOW=Instant.parse("2026-11-03T12:00:00Z");
  static final Clock CLOCK=Clock.fixed(NOW,ZoneOffset.UTC);
  static final UUID ACTOR=new UUID(0,1), TENANT=new UUID(0,2), SUBJECT=new UUID(0,3), RESOURCE=new UUID(0,4), SESSION=new UUID(0,5), OTHER=new UUID(0,99);

  /** SYNTHETIC_TEST_ONLY: never registered with any production verifier or HTTP route. */
  static final class SyntheticTestFactory {
    static TrustedRequestContext valid(Role role) {
      UUID actor=role==Role.CLIENT?SUBJECT:ACTOR;
      Purpose purpose=role==Role.CLIENT?Purpose.SELF_ACCESS:Purpose.COACHING_SUPPORT;
      Map<Gate,Evidence> proofs=new EnumMap<>(Gate.class);
      for (Gate gate:Gate.values()) proofs.put(gate,new Evidence(gate,actor,TENANT,SUBJECT,RESOURCE,purpose,Operation.SENSITIVE_CLIENT_READ,"synthetic-policy-v1","synthetic-"+gate,1,State.CURRENT,NOW.minusSeconds(60),NOW.plusSeconds(60),null));
      return new TrustedRequestContext(actor,TENANT,SUBJECT,RESOURCE,SESSION,role,purpose,Operation.SENSITIVE_CLIENT_READ,1,proofs);
    }
  }
  static Request request(TrustedRequestContext c) { return new Request(c.principal,c.tenant,c.subject,c.resource,c.purpose,c.operation,c.revision); }
  static CoachClientAccessService service(TrustedRequestContext c) { return new CoachClientAccessService(new OwnerGuard(CLOCK,r->c)); }
  static TrustedRequestContext withProof(TrustedRequestContext c,Gate gate,Evidence proof) {
    Map<Gate,Evidence> map=new EnumMap<>(c.evidence); if(proof==null)map.remove(gate);else map.put(gate,proof);
    return new TrustedRequestContext(c.principal,c.tenant,c.subject,c.resource,c.authSession,c.role,c.purpose,c.operation,c.revision,map);
  }
  static Evidence alter(Evidence p,State state,Instant expires,Instant revoked,long revision) {
    return new Evidence(p.gate(),p.principal(),p.tenant(),p.subject(),p.resource(),p.purpose(),p.operation(),p.policyRef(),p.decisionRef(),revision,state,p.effectiveAt(),expires,revoked);
  }
  @Test void assignedCoachWithAllIndependentGatesAllowsSyntheticScope() {
    var c=SyntheticTestFactory.valid(Role.COACH);var d=service(c).authorizeSensitiveClientRead(request(c));
    assertTrue(d.allowed());assertEquals(ALLOW_SYNTHETIC_DOMAIN_SCOPE,d.reason());assertEquals(7,d.decisionReferences().size());
  }
  @Test void clientOwnResourceAllowsSyntheticScopeWithoutCoachAssignment() {
    var c=withProof(SyntheticTestFactory.valid(Role.CLIENT),Gate.ASSIGNMENT,null);
    assertTrue(service(c).authorizeSensitiveClientRead(request(c)).allowed());
  }
  @Test void crossTenantIsDenied() { var c=SyntheticTestFactory.valid(Role.COACH);assertEquals(CONTEXT_MISMATCH,service(c).authorizeSensitiveClientRead(new Request(ACTOR,OTHER,SUBJECT,RESOURCE,c.purpose,c.operation,1)).reason()); }
  @Test void wrongSubjectIsDenied() { var c=SyntheticTestFactory.valid(Role.COACH);assertEquals(CONTEXT_MISMATCH,service(c).authorizeSensitiveClientRead(new Request(ACTOR,TENANT,OTHER,RESOURCE,c.purpose,c.operation,1)).reason()); }
  @Test void wrongResourceIsDenied() { var c=SyntheticTestFactory.valid(Role.COACH);assertEquals(CONTEXT_MISMATCH,service(c).authorizeSensitiveClientRead(new Request(ACTOR,TENANT,SUBJECT,OTHER,c.purpose,c.operation,1)).reason()); }
  @Test void assignmentCannotBeInferredFromOtherGates() { var c=withProof(SyntheticTestFactory.valid(Role.COACH),Gate.ASSIGNMENT,null);assertEquals(EVIDENCE_MISSING,service(c).authorizeSensitiveClientRead(request(c)).reason()); }
  @Test void eachMissingGateDeniesIndependently() {
    for(Gate g:Gate.values()){var c=withProof(SyntheticTestFactory.valid(Role.COACH),g,null);assertEquals(EVIDENCE_MISSING,service(c).authorizeSensitiveClientRead(request(c)).reason(),g.name());}
  }
  @Test void consentWithoutShareDenies() { var c=withProof(SyntheticTestFactory.valid(Role.COACH),Gate.SHARE,null);assertFalse(service(c).authorizeSensitiveClientRead(request(c)).allowed()); }
  @Test void shareWithoutConsentDenies() { var c=withProof(SyntheticTestFactory.valid(Role.COACH),Gate.CONSENT,null);assertFalse(service(c).authorizeSensitiveClientRead(request(c)).allowed()); }
  @Test void entitlementAbsentDenies() { var c=withProof(SyntheticTestFactory.valid(Role.COACH),Gate.ENTITLEMENT,null);assertFalse(service(c).authorizeSensitiveClientRead(request(c)).allowed()); }
  @Test void allExpiredRevokedStaleUnknownAndDeniedGatesDenyIndependently() {
    for(Gate g:Gate.values())for(State state:State.values()) {
      if(state==State.CURRENT)continue;
      var c=SyntheticTestFactory.valid(Role.COACH);var p=c.evidence.get(g);
      var changed=withProof(c,g,alter(p,state,p.expiresAt(),null,1));
      assertEquals(EVIDENCE_NOT_CURRENT,service(changed).authorizeSensitiveClientRead(request(c)).reason(),g+":"+state);
    }
  }
  @Test void expiryAndRevocationAtExactClockDenyEveryGate() {
    for(Gate g:Gate.values()) {
      var c=SyntheticTestFactory.valid(Role.COACH);var p=c.evidence.get(g);
      for(Evidence proof:List.of(alter(p,State.CURRENT,NOW,null,1),alter(p,State.CURRENT,p.expiresAt(),NOW,1)))
        assertEquals(EVIDENCE_TIME_INVALID,service(withProof(c,g,proof)).authorizeSensitiveClientRead(request(c)).reason());
    }
  }
  @Test void staleEvidenceRevisionDenies() { var c=SyntheticTestFactory.valid(Role.COACH);var p=c.evidence.get(Gate.CONSENT);assertEquals(EVIDENCE_BINDING_MISMATCH,service(withProof(c,Gate.CONSENT,alter(p,State.CURRENT,p.expiresAt(),null,2))).authorizeSensitiveClientRead(request(c)).reason()); }
  @Test void futureDatedAndUnboundEvidenceDeny() {
    var c=SyntheticTestFactory.valid(Role.COACH);var p=c.evidence.get(Gate.SHARE);
    var future=new Evidence(p.gate(),p.principal(),p.tenant(),p.subject(),p.resource(),p.purpose(),p.operation(),p.policyRef(),p.decisionRef(),1,State.CURRENT,NOW.plusSeconds(1),p.expiresAt(),null);
    assertEquals(EVIDENCE_TIME_INVALID,service(withProof(c,Gate.SHARE,future)).authorizeSensitiveClientRead(request(c)).reason());
    var foreign=new Evidence(p.gate(),p.principal(),OTHER,p.subject(),p.resource(),p.purpose(),p.operation(),p.policyRef(),p.decisionRef(),1,State.CURRENT,p.effectiveAt(),p.expiresAt(),null);
    assertEquals(EVIDENCE_BINDING_MISMATCH,service(withProof(c,Gate.SHARE,foreign)).authorizeSensitiveClientRead(request(c)).reason());
    var noRef=new Evidence(p.gate(),p.principal(),p.tenant(),p.subject(),p.resource(),p.purpose(),p.operation(),"",p.decisionRef(),1,State.CURRENT,p.effectiveAt(),p.expiresAt(),null);
    assertEquals(EVIDENCE_BINDING_MISMATCH,service(withProof(c,Gate.SHARE,noRef)).authorizeSensitiveClientRead(request(c)).reason());
  }
  @Test void nullRequestAndMissingSessionDeny() {
    assertEquals(REQUEST_INVALID,new OwnerGuard(CLOCK).authorize(null).reason());
    var c=SyntheticTestFactory.valid(Role.COACH);
    var noSession=new TrustedRequestContext(c.principal,c.tenant,c.subject,c.resource,null,c.role,c.purpose,c.operation,c.revision,c.evidence);
    assertEquals(CONTEXT_MISMATCH,service(noSession).authorizeSensitiveClientRead(request(c)).reason());
  }
  @Test void tenantAdminAndServiceRolesCannotBypassSensitiveScope() {
    for(Role r:Role.values())if(r!=Role.COACH&&r!=Role.CLIENT){var c=SyntheticTestFactory.valid(r);assertEquals(ROLE_SCOPE_DENIED,service(c).authorizeSensitiveClientRead(request(c)).reason(),r.name());}
  }
  @Test void unknownPurposeAndOperationDeny() { var c=SyntheticTestFactory.valid(Role.COACH);assertEquals(REQUEST_INVALID,service(c).authorizeSensitiveClientRead(new Request(ACTOR,TENANT,SUBJECT,RESOURCE,Purpose.UNKNOWN,c.operation,1)).reason());assertEquals(REQUEST_INVALID,service(c).authorizeSensitiveClientRead(new Request(ACTOR,TENANT,SUBJECT,RESOURCE,c.purpose,Operation.UNKNOWN,1)).reason()); }
  @Test void injectedCallerIdentityCannotBecomeTrusted() { var c=SyntheticTestFactory.valid(Role.COACH);var d=service(c).authorizeSensitiveClientRead(new Request(OTHER,TENANT,SUBJECT,RESOURCE,c.purpose,c.operation,1));assertEquals(CONTEXT_MISMATCH,d.reason());assertTrue(d.decisionReferences().isEmpty()); }
  @Test void noLivePiacDefaultDeniesEvenPlausibleCallerFields() { var c=SyntheticTestFactory.valid(Role.COACH);assertEquals(PIAC_NOT_CONNECTED,new CoachClientAccessService(new OwnerGuard(CLOCK)).authorizeSensitiveClientRead(request(c)).reason()); }
  @Test void trustSourceErrorsDenyWithoutLeakingErrorPayload() { var c=SyntheticTestFactory.valid(Role.COACH);var guard=new OwnerGuard(CLOCK,r->{throw new IllegalStateException("private synthetic payload");});var d=guard.authorize(request(c));assertEquals(TRUST_UNAVAILABLE,d.reason());assertFalse(d.toString().contains("private")); }
  @Test void noHttpOrJarLiveReadinessChange() {
    assertFalse(TrustedPiacVerifier.NONE.verifiesLiveIdentity());
    assertFalse(Arrays.stream(TrustedRequestContext.class.getConstructors()).findAny().isPresent());
    assertFalse(Arrays.stream(OwnerGuard.class.getAnnotations()).anyMatch(a->a.annotationType().getName().contains("Controller")));
  }
}
