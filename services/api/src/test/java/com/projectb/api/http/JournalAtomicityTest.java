package com.projectb.api.http;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import com.projectb.api.domain.JourneyJournal;
import com.projectb.api.domain.JourneyJournal.JournalCommit;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.AssignmentView;
import com.projectb.api.domain.JourneyKernel.CanonicalPin;
import com.projectb.api.domain.JourneyKernel.DomainException;
import com.projectb.api.domain.JourneyKernel.DraftView;
import com.projectb.api.domain.JourneyKernel.ErrorCode;
import com.projectb.api.domain.JourneyKernel.PublishedView;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.domain.JourneyKernel.Step;

/** ARC-01: durable commit, partial writes, restart, idempotency, and withdrawal. */
public final class JournalAtomicityTest {
  private static final String TENANT = "11111111-1111-4111-8111-111111111111";
  private static final String COACH = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  private static final String CLIENT = "33333333-3333-4333-8333-333333333333";
  private static final String SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  private static final Actor ACTOR = new Actor(TENANT, COACH, Role.COACH);

  public static void main(String[] args) throws Exception {
    failedAppendDoesNotAuthorize();
    partialTailIsDiscarded();
    interiorCorruptionFailsClosed();
    idempotentRecordsStaySingularAcrossRestart();
    withdrawalSurvivesRestartAndRejectsANewKey();
    httpMapsCommitFailureToClosedResponse();
    System.out.println("PASS JournalAtomicityTest append_failure=isolated partial_tail=discarded interior_corruption=fail_closed idempotency=stable withdrawal_replay=denied http_persistence=503");
  }

  private static void failedAppendDoesNotAuthorize() throws Exception {
    Path dir = Files.createTempDirectory("arcava-atomic");
    Path journal = dir.resolve("journal.ndjson");
    Files.createFile(journal);
    JourneyJournal live = JourneyJournal.open(journal);
    Files.delete(journal);
    Files.createDirectory(journal);
    boolean threw = false;
    try {
      live.createDraft(ACTOR, "Synthetic resilience", "create-1");
    } catch (java.io.IOException ex) {
      threw = true;
    }
    check(threw, "append failure must not return success");
    Files.delete(journal);
    DraftView created = live.createDraft(ACTOR, "Other title", "create-1");
    check("Other title".equals(created.title()), "failed append must not keep the idempotency key");
    JourneyJournal restarted = JourneyJournal.open(journal);
    DraftView again = restarted.createDraft(ACTOR, "Other title", "create-1");
    check(created.draftId().equals(again.draftId()), "restart returns the committed draft");
    check(lines(journal) == 1, "one committed create");
  }

  private static void partialTailIsDiscarded() throws Exception {
    Path journal = file();
    JourneyJournal live = JourneyJournal.open(journal);
    DraftView draft = live.createDraft(ACTOR, "Synthetic resilience", "create-1");
    Files.write(journal, "SHORT".getBytes(StandardCharsets.UTF_8), StandardOpenOption.APPEND);
    JourneyJournal restarted = JourneyJournal.open(journal);
    String stored = Files.readString(journal);
    check(stored.endsWith("\n") && !stored.contains("SHORT"), "uncommitted tail removed");
    check(draft.draftId().equals(restarted.createDraft(ACTOR, "Synthetic resilience", "create-1").draftId()), "committed draft kept");
    JournalCommit shortWrite = (path, line) -> {
      Files.write(path, "PARTIAL".getBytes(StandardCharsets.UTF_8), StandardOpenOption.APPEND);
      throw new java.io.IOException("injected short write");
    };
    JourneyJournal injected = JourneyJournal.open(journal, shortWrite);
    boolean shortFailed = false;
    try {
      injected.createDraft(ACTOR, "Second", "create-2");
    } catch (java.io.IOException ex) {
      shortFailed = true;
    }
    check(shortFailed, "short write fails closed");
    JourneyJournal after = JourneyJournal.open(journal);
    check(!Files.readString(journal).contains("PARTIAL"), "short write is not a committed record");
    after.createDraft(ACTOR, "Second", "create-2");
    check(after.createDraft(ACTOR, "Synthetic resilience", "create-1").draftId().equals(draft.draftId()), "earlier commit remains");
  }

  private static void interiorCorruptionFailsClosed() throws Exception {
    Path journal = file();
    JourneyJournal live = JourneyJournal.open(journal);
    live.createDraft(ACTOR, "Synthetic resilience", "create-1");
    Files.writeString(journal, "{\"op\":\"bogus\"}\n{\"op\":\"create\",\"tenant_id\":\"" + TENANT
        + "\",\"subject_id\":\"" + COACH + "\",\"key\":\"create-2\",\"title\":\"Skipped\",\"draft_id\":\""
        + UUID.randomUUID() + "\"}\n", StandardOpenOption.APPEND);
    boolean failed = false;
    try {
      JourneyJournal.open(journal);
    } catch (java.io.IOException ex) {
      failed = ex.getMessage().contains("not recoverable");
    }
    check(failed, "malformed interior record must not be skipped");
  }

  private static void idempotentRecordsStaySingularAcrossRestart() throws Exception {
    Path journal = file();
    JourneyJournal live = JourneyJournal.open(journal);
    DraftView draft = live.createDraft(ACTOR, "Synthetic resilience", "create-1");
    live.createDraft(ACTOR, "Synthetic resilience", "create-1");
    live.updateDraft(ACTOR, draft.draftId(), 1, "Synthetic resilience", steps(), null);
    PublishedView published = live.publish(ACTOR, draft.draftId(), 2, "publish-1");
    PublishedView publishedAgain = live.publish(ACTOR, draft.draftId(), 2, "publish-1");
    AssignmentView assigned = live.assign(ACTOR, CLIENT, published.journeyVersionId(), true, "assign-1");
    AssignmentView assignedAgain = live.assign(ACTOR, CLIENT, published.journeyVersionId(), true, "assign-1");
    check(published.journeyVersionId().equals(publishedAgain.journeyVersionId()), "publish replay");
    check(assigned.assignmentId().equals(assignedAgain.assignmentId()), "assign replay");
    long committed = lines(journal);
    JourneyJournal restarted = JourneyJournal.open(journal);
    check(lines(journal) == committed, "restart does not rewrite history");
    check(draft.draftId().equals(restarted.createDraft(ACTOR, "Synthetic resilience", "create-1").draftId()), "create id");
    check(published.journeyVersionId().equals(restarted.publish(ACTOR, draft.draftId(), 2, "publish-1").journeyVersionId()), "publish id");
    check(assigned.assignmentId().equals(restarted.assign(ACTOR, CLIENT, published.journeyVersionId(), true, "assign-1").assignmentId()), "assign id");
  }

  private static void withdrawalSurvivesRestartAndRejectsANewKey() throws Exception {
    Path journal = file();
    JourneyJournal prepared = JourneyJournal.open(journal);
    DraftView draft = prepared.createDraft(ACTOR, "Synthetic resilience", "create-1");
    prepared.updateDraft(ACTOR, draft.draftId(), 1, "Synthetic resilience", steps(), "[]");
    PublishedView published = prepared.publish(ACTOR, draft.draftId(), 2, "publish-1");
    prepared.assign(ACTOR, CLIENT, published.journeyVersionId(), true, "assign-1");
    long before = lines(journal);
    JourneyJournal blocked = JourneyJournal.open(journal, (path, line) -> {
      throw new java.io.IOException("injected append failure");
    });
    boolean withdrawFailed = false;
    try {
      blocked.withdraw(ACTOR, published.journeyVersionId());
    } catch (java.io.IOException ex) {
      withdrawFailed = true;
    }
    check(withdrawFailed, "withdraw append failure");
    check(lines(journal) == before, "failed withdraw writes nothing");
    check("published".equals(blocked.kernel().readPublishedForCoach(ACTOR, published.journeyVersionId()).status()), "memory stays published when withdraw is not committed");
    check("PUBLISHED".equals(JourneyJournal.open(journal).projection(published.journeyVersionId()).publicationState()), "disk stays published");
    JourneyJournal live = JourneyJournal.open(journal);
    PublishedView withdrawn = live.withdraw(ACTOR, published.journeyVersionId());
    check("revoked".equals(withdrawn.status()), "withdraw commits");
    check("WITHDRAWN".equals(live.projection(published.journeyVersionId()).publicationState()), "projection withdrawn");
    live.withdraw(ACTOR, published.journeyVersionId());
    check(lines(journal) == before + 1, "second withdraw does not append");
    expectWithdrawn(() -> live.assign(ACTOR, CLIENT, published.journeyVersionId(), true, "assign-1"));
    expectWithdrawn(() -> live.assign(ACTOR, CLIENT, published.journeyVersionId(), true, "assign-2"));
    JourneyJournal restarted = JourneyJournal.open(journal);
    check("WITHDRAWN".equals(restarted.projection(published.journeyVersionId()).publicationState()), "withdrawal survives restart");
    expectWithdrawn(() -> restarted.assign(ACTOR, CLIENT, published.journeyVersionId(), true, "assign-1"));
    expectWithdrawn(() -> restarted.assign(ACTOR, CLIENT, published.journeyVersionId(), true, "assign-2"));
  }

  private static void httpMapsCommitFailureToClosedResponse() throws Exception {
    Path journal = file();
    JourneyJournal live = JourneyJournal.open(journal, (path, line) -> {
      throw new java.io.IOException("injected append failure");
    });
    Map<String, Actor> tokens = Map.of("coach-a", ACTOR);
    JourneyHttpServer server = JourneyHttpServer.start(live, tokens, Set.of());
    try {
      HttpResponse<String> response = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build().send(
          HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + server.port() + "/project-b/v1/tenants/" + TENANT + "/journeys/drafts"))
              .timeout(Duration.ofSeconds(3))
              .header("Authorization", "Bearer coach-a")
              .header("Idempotency-Key", "create-1")
              .header("Content-Type", "application/json")
              .POST(HttpRequest.BodyPublishers.ofString("{\"title\":\"Synthetic resilience\"}"))
              .build(),
          HttpResponse.BodyHandlers.ofString());
      check(response.statusCode() == 503 && response.body().contains("PERSISTENCE_FAILED"), "http persistence " + response.statusCode() + " " + response.body());
    } finally {
      server.stop();
    }
    check(lines(journal) == 0, "failed http create is not durable");
  }

  private static void expectWithdrawn(Attempt attempt) {
    try {
      attempt.run();
      throw new AssertionError("assignment authorized withdrawn content");
    } catch (DomainException ex) {
      check(ex.code == ErrorCode.WITHDRAWN, "withdrawal code " + ex.code);
    } catch (RuntimeException ex) {
      throw ex;
    } catch (Exception ex) {
      throw new AssertionError(ex);
    }
  }

  private interface Attempt { void run() throws Exception; }

  private static List<Step> steps() {
    return List.of(new Step("66666666-6666-4666-8666-666666666666", "Breathing",
        new CanonicalPin("kdb:protocol:published-version-v1", SHA, true, true)));
  }

  private static Path file() throws Exception {
    return Files.createTempDirectory("arcava-atomic").resolve("journal.ndjson");
  }

  private static long lines(Path path) throws Exception {
    if (!Files.exists(path)) return 0;
    return Files.readAllLines(path).stream().filter(line -> !line.isBlank()).count();
  }

  private static void check(boolean condition, String label) {
    if (!condition) throw new AssertionError(label);
  }
}
