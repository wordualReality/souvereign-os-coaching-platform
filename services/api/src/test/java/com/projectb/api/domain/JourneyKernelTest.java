package com.projectb.api.domain;

import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import com.projectb.api.domain.JourneyKernel.*;

/** Deterministic fixture-based checks; not a producer or PIAC integration test. */
public final class JourneyKernelTest {
  private static final AtomicInteger checks = new AtomicInteger();
  private static void check(boolean condition, String label) {
    if (!condition) throw new AssertionError(label);
    checks.incrementAndGet();
  }
  private static void rejects(ErrorCode code, Runnable run) {
    try { run.run(); }
    catch (DomainException ex) {
      check(ex.code == code, "expected " + code + ", saw " + ex.code);
      return;
    }
    throw new AssertionError("Expected " + code);
  }
  public static void main(String[] args) {
    JourneyKernel kernel = new JourneyKernel();
    Actor coachA = new Actor("tenant-a", "coach-a", Role.COACH);
    Actor coachB = new Actor("tenant-b", "coach-b", Role.COACH);
    Actor clientA = new Actor("tenant-a", "client-a", Role.CLIENT);
    Actor otherClient = new Actor("tenant-a", "other-client", Role.CLIENT);
    CanonicalPin pin = new CanonicalPin("kdb:protocol:published-version-v1",
             "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", true, true);
    DraftView draft = kernel.createDraft(coachA, "tenant-a", "Synthetic resilience", "create-1");
    check(draft.revision() == 1, "draft initial revision");
    check(!kernel.createDraft(coachB,"tenant-b","Synthetic resilience","create-1").draftId().equals(draft.draftId()), "tenant-scoped idempotency keys");
    check(kernel.createDraft(coachA,"tenant-a","Synthetic resilience","create-1").draftId().equals(draft.draftId()), "create replay");
    rejects(ErrorCode.IDEMPOTENCY_CONFLICT, () -> kernel.createDraft(coachA,"tenant-a","different","create-1"));
    rejects(ErrorCode.FORBIDDEN, () -> kernel.updateDraft(coachB,"tenant-a",draft.draftId(),1,"updated",List.of(new Step("step-1","Breathing",pin))));
    rejects(ErrorCode.INVALID, () -> kernel.updateDraft(coachA,"tenant-a",draft.draftId(),1,"updated",List.of()));
    DraftView ready = kernel.updateDraft(coachA,"tenant-a",draft.draftId(),1,"Synthetic resilience",List.of(new Step("step-1","Breathing",pin)));
    check(ready.revision() == 2, "revision increased");
    rejects(ErrorCode.STALE_REVISION, () -> kernel.updateDraft(coachA,"tenant-a",draft.draftId(),1,"stale",ready.steps()));
    rejects(ErrorCode.STALE_REVISION, () -> kernel.publish(coachA,"tenant-a",draft.draftId(),1,"publish-stale"));
    PublishedView published = kernel.publish(coachA,"tenant-a",draft.draftId(),2,"publish-1");
    check(published.version() == 2 && published.status().equals("published"), "immutable version published");
    check(published.immutableSteps().size() == 1, "version carries pinned immutable steps");
    check(kernel.publish(coachA,"tenant-a",draft.draftId(),2,"publish-1").journeyVersionId().equals(published.journeyVersionId()),"publish replay");
    rejects(ErrorCode.INVALID, () -> kernel.updateDraft(coachA,"tenant-a",draft.draftId(),2,"mutate",ready.steps()));
    rejects(ErrorCode.CONSENT_REQUIRED, () -> kernel.assign(coachA,"tenant-a","client-a",published.journeyVersionId(),false,"assign-no-consent"));
    rejects(ErrorCode.FORBIDDEN, () -> kernel.assign(coachB,"tenant-a","client-a",published.journeyVersionId(),true,"assign-cross-tenant"));
    AssignmentView a = kernel.assign(coachA,"tenant-a","client-a",published.journeyVersionId(),true,"assign-1");
    check(a.status().equals("active"), "active assignment created");
    check(kernel.assign(coachA,"tenant-a","client-a",published.journeyVersionId(),true,"assign-1").assignmentId().equals(a.assignmentId()), "assign replay");
    rejects(ErrorCode.IDEMPOTENCY_CONFLICT, () -> kernel.assign(coachA,"tenant-a","different-client",published.journeyVersionId(),true,"assign-1"));
    check(kernel.readAssignedVersion(clientA,"tenant-a",a.assignmentId()).journeyVersionId().equals(published.journeyVersionId()),"client gets pinned version");
    rejects(ErrorCode.FORBIDDEN, () -> kernel.readAssignedVersion(otherClient,"tenant-a",a.assignmentId()));
    rejects(ErrorCode.FORBIDDEN, () -> kernel.readAssignedVersion(clientA,"tenant-b",a.assignmentId()));
    check(kernel.withdraw(coachA,"tenant-a",published.journeyVersionId()).status().equals("revoked"),"withdraw");
    check(kernel.publish(coachA,"tenant-a",draft.draftId(),2,"publish-1").status().equals("revoked"), "publish replay returns current revoked state");
    rejects(ErrorCode.WITHDRAWN, () -> kernel.assign(coachA,"tenant-a","client-a",published.journeyVersionId(),true,"assign-1"));
    rejects(ErrorCode.WITHDRAWN, () -> kernel.readAssignedVersion(clientA,"tenant-a",a.assignmentId()));
    rejects(ErrorCode.WITHDRAWN, () -> kernel.assign(coachA,"tenant-a","client-b",published.journeyVersionId(),true,"assign-after-withdrawal"));
    DraftView invalid = kernel.createDraft(coachA,"tenant-a","No proof","create-bad-proof");
    kernel.updateDraft(coachA,"tenant-a",invalid.draftId(),1,"No proof",List.of(new Step("s2","Not reviewed",new CanonicalPin("kdb:unreviewed","bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",false,false))));
    rejects(ErrorCode.UNPUBLISHED_CANONICAL, () -> kernel.publish(coachA,"tenant-a",invalid.draftId(),2,"publish-bad-proof"));
    System.out.println("PASS JourneyKernelTest checks=" + checks.get() + " synthetic=true, externalAuth=false, kdbVerified=false");
  }
}
