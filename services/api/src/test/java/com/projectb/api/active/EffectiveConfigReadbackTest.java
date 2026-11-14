package com.projectb.api.active;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Duration;
import com.projectb.api.Application;
import org.junit.jupiter.api.Test;
import org.springframework.boot.SpringApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.env.Environment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class EffectiveConfigReadbackTest {
  private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

  @Test
  void effectiveReadbackMatchesTheRunningBindAndRedactsTheJournalPath() throws Exception {
    Path journal = Files.createTempDirectory("arcava-effective").resolve("journal.ndjson");
    ConfigurableApplicationContext context = new SpringApplication(Application.class).run(
        "--server.port=0",
        "--server.address=127.0.0.1",
        "--spring.profiles.active=dev",
        "--arcava.journal.path=" + journal);
    try {
      int port = Integer.parseInt(context.getBean(Environment.class).getProperty("local.server.port"));
      HttpResponse<String> body = http.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/health/effective"))
          .timeout(Duration.ofSeconds(3)).GET().build(), HttpResponse.BodyHandlers.ofString());
      assertThat(body.statusCode()).isEqualTo(200);
      assertThat(body.body()).contains("\"SERVER_ADDRESS\":\"127.0.0.1\"");
      assertThat(body.body()).contains("\"SERVER_PORT\":" + port);
      assertThat(body.body()).contains("\"ARCAVA_RUNTIME_ROLE\":\"ACTIVE_DEV_HTTP\"");
      assertThat(body.body()).contains("\"SPRING_PROFILES_ACTIVE\":\"dev\"");
      assertThat(body.body()).contains("\"ARCAVA_JOURNAL_PATH_PRESENT\":true");
      assertThat(body.body()).contains("\"ARCAVA_JOURNAL_PATH_SHA256\":\"" + sha256(journal.toString()) + "\"");
      assertThat(body.body()).doesNotContain(journal.toString());
      assertThat(body.body()).doesNotContain("DATABASE_URL", "SUPABASE_SERVICE_ROLE_KEY");
      assertThat(body.body()).contains("\"e1_authority\":\"NOT_ADMITTED\"");
      assertThat(body.body()).contains("\"e1_reason\":\"LIVE_AUTHORITY_CLOSED\"");
      assertThat(body.body()).contains("\"piac_transport\":\"not_connected\"");
      assertThat(body.body()).contains("\"kdb_transport\":\"not_connected\"");
      assertThat(http.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/health/ready"))
          .timeout(Duration.ofSeconds(3)).GET().build(), HttpResponse.BodyHandlers.ofString()).statusCode())
          .isEqualTo(503);
    } finally {
      context.close();
    }
  }

  @Test
  void blankJournalPathFailsClosed() {
    assertThatThrownBy(() -> new SpringApplication(Application.class).run(
        "--server.port=0",
        "--server.address=127.0.0.1",
        "--arcava.journal.path="))
        .hasRootCauseMessage("arcava.journal.path is required");
  }

  private static String sha256(String value) throws Exception {
    byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
    StringBuilder hex = new StringBuilder(digest.length * 2);
    for (byte b : digest) hex.append(String.format("%02x", b));
    return hex.toString();
  }
}
