package com.projectb.api.active;

import java.net.ConnectException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import com.projectb.api.Application;
import com.projectb.api.domain.JourneyJournal;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.CanonicalPin;
import com.projectb.api.domain.JourneyKernel.DraftView;
import com.projectb.api.domain.JourneyKernel.PublishedView;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.domain.JourneyKernel.Step;
import org.junit.jupiter.api.Test;
import org.springframework.boot.SpringApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.env.Environment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ActiveDevHttpLifecycleTest {
  private static final String TENANT = "11111111-1111-4111-8111-111111111111";
  private static final String COACH = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  private static final String SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  private static final Actor ACTOR = new Actor(TENANT, COACH, Role.COACH);
  private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

  @Test
  void listenerStartsReportsClosedReadinessAndStopsCleanly() throws Exception {
    Path journal = Files.createTempDirectory("arcava-active").resolve("journal.ndjson");
    DraftView draft = seed(journal);
    byte[] before = Files.readAllBytes(journal);
    ConfigurableApplicationContext first = start(journal);
    int port = port(first);
    try {
      HttpResponse<String> live = get(port, "/health/live");
      assertThat(live.statusCode()).isEqualTo(200);
      assertThat(live.body()).contains("ACTIVE_DEV_HTTP", "\"live_authority\":\"closed\"");
      assertThat(live.body()).doesNotContain("NON_WEB_INACTIVE_BOOTSTRAP");
      assertThat(get(port, "/health/ready").statusCode()).isEqualTo(503);
      assertThat(post(port, "/project-b/v1/tenants/" + TENANT + "/producers/CT-ARC-003", null,
          "{\"consent_verified\":true,\"forged-grant\":true}").statusCode()).isEqualTo(401);
      HttpResponse<String> denied = post(port, "/project-b/v1/tenants/" + TENANT + "/producers/CT-ARC-004", "coach-a",
          "{\"consent_verified\":true,\"publication_state\":\"PUBLISHED\",\"runtime_session_refs\":[\"sov-session\"],\"outcome\":\"OK\",\"forged-grant\":true}");
      assertThat(denied.statusCode()).isEqualTo(403);
      assertThat(denied.body()).contains("LIVE_AUTHORITY_CLOSED");
      assertThat(denied.body()).doesNotContain("sov-session", "forged-grant", "\"outcome\":\"OK\"");
      HttpResponse<String> foreign = post(port, "/project-b/v1/tenants/99999999-9999-4999-8999-999999999999/producers/CT-ARC-002",
          "coach-a", "{\"client_id\":\"other-client\"}");
      assertThat(foreign.statusCode()).isEqualTo(403);
      assertThat(foreign.body()).contains("LIVE_AUTHORITY_CLOSED");
      HttpRequest badCorrelation = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port
          + "/project-b/v1/tenants/" + TENANT + "/producers/CT-ARC-003"))
          .timeout(Duration.ofSeconds(3))
          .header("authorization", "Bearer coach-a")
          .header("x-correlation-id", "not-a-uuid")
          .header("content-type", "application/json")
          .POST(HttpRequest.BodyPublishers.ofString("{}"))
          .build();
      assertThat(http.send(badCorrelation, HttpResponse.BodyHandlers.ofString()).statusCode()).isEqualTo(422);
      post(port, "/project-b/v1/tenants/" + TENANT + "/producers/CT-ARC-002", "coach-a", "{}");
      assertThat(Files.readAllBytes(journal)).isEqualTo(before);
    } finally {
      first.close();
    }
    assertThatThrownBy(() -> get(port, "/health/live")).isInstanceOf(ConnectException.class);
    ConfigurableApplicationContext second = start(journal);
    try {
      assertThat(get(port(second), "/health/live").statusCode()).isEqualTo(200);
      assertThat(Files.readAllBytes(journal)).isEqualTo(before);
      JourneyJournal reopened = JourneyJournal.open(journal);
      assertThat(reopened.kernel().readDraft(ACTOR, draft.draftId()).draftId()).isEqualTo(draft.draftId());
    } finally {
      second.close();
    }
  }

  @Test
  void withdrawnJournalProjectionStaysWithdrawn() throws Exception {
    Path journal = Files.createTempDirectory("arcava-withdrawn").resolve("journal.ndjson");
    JourneyJournal prepared = JourneyJournal.open(journal);
    DraftView draft = prepared.createDraft(ACTOR, "Synthetic resilience", "create-1");
    prepared.updateDraft(ACTOR, draft.draftId(), 1, "Synthetic resilience", steps(), "[]");
    PublishedView published = prepared.publish(ACTOR, draft.draftId(), 2, "publish-1");
    prepared.withdraw(ACTOR, published.journeyVersionId());
    byte[] before = Files.readAllBytes(journal);
    ConfigurableApplicationContext context = start(journal);
    try {
      HttpResponse<String> denied = post(port(context),
          "/project-b/v1/tenants/" + TENANT + "/producers/CT-ARC-003", "coach-a",
          "{\"consent_verified\":true}");
      assertThat(denied.statusCode()).isEqualTo(403);
      assertThat(Files.readAllBytes(journal)).isEqualTo(before);
    } finally {
      context.close();
    }
    JourneyJournal reopened = JourneyJournal.open(journal);
    assertThat(reopened.projection(published.journeyVersionId()).publicationState()).isEqualTo("WITHDRAWN");
  }

  @Test
  void nonLoopbackBindFailsBeforeListening() throws Exception {
    Path journal = Files.createTempDirectory("arcava-bind").resolve("journal.ndjson");
    assertThatThrownBy(() -> new SpringApplication(Application.class).run(
        "--server.port=0", "--server.address=0.0.0.0", "--arcava.journal.path=" + journal))
        .hasRootCauseMessage("active dev runtime refuses a non-loopback bind");
  }

  private static DraftView seed(Path journal) throws Exception {
    return JourneyJournal.open(journal).createDraft(ACTOR, "Synthetic resilience", "create-1");
  }

  private static ConfigurableApplicationContext start(Path journal) {
    return new SpringApplication(Application.class).run(
        "--server.port=0", "--server.address=127.0.0.1", "--arcava.journal.path=" + journal);
  }

  private static int port(ConfigurableApplicationContext context) {
    return Integer.parseInt(context.getBean(Environment.class).getProperty("local.server.port"));
  }

  private HttpResponse<String> get(int port, String path) throws Exception {
    HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
        .timeout(Duration.ofSeconds(3)).GET().build();
    return http.send(request, HttpResponse.BodyHandlers.ofString());
  }

  private HttpResponse<String> post(int port, String path, String bearer, String body) throws Exception {
    HttpRequest.Builder request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
        .timeout(Duration.ofSeconds(3))
        .header("content-type", "application/json")
        .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8));
    if (bearer != null) request.header("authorization", "Bearer " + bearer);
    return http.send(request.build(), HttpResponse.BodyHandlers.ofString());
  }

  private static List<Step> steps() {
    return List.of(new Step(UUID.randomUUID().toString(), "Breathing",
        new CanonicalPin("kdb:protocol:published-version-v1", SHA, true, true)));
  }
}
