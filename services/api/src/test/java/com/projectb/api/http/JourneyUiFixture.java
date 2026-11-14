package com.projectb.api.http;

import static com.projectb.api.http.JourneyPathTest.*;

import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.Role;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Set;

/** Disposable, synthetic loopback launcher used by the UI smoke. */
public final class JourneyUiFixture {
  public static void main(String[] args) throws Exception {
    if (args.length != 2 || !Set.of("seed", "replay", "no-consent").contains(args[1]))
      throw new IllegalArgumentException("expected journal path and seed or replay");
    Path journal = Path.of(args[0]);
    boolean seed = "seed".equals(args[1]);
    if (seed == Files.exists(journal)) throw new IllegalArgumentException("unexpected journal state");

    String coach = System.getenv("ARCAVA_UI01_COACH_BEARER");
    String client = System.getenv("ARCAVA_UI01_CLIENT_BEARER");
    if (coach == null || coach.isBlank() || client == null || client.isBlank() || coach.equals(client))
      throw new IllegalArgumentException("distinct synthetic bearer tokens required");
    var tokens = new java.util.HashMap<>(Map.of(
        coach, new Actor(TENANT_A, COACH_A, Role.COACH),
        client, new Actor(TENANT_A, CLIENT_A, Role.CLIENT)));
    String otherCoach = System.getenv("ARCAVA_UI02_OTHER_COACH");
    String otherClient = System.getenv("ARCAVA_UI02_OTHER_CLIENT");
    if (otherCoach != null) tokens.put(otherCoach, new Actor(TENANT_A, "other-coach", Role.COACH));
    if (otherClient != null) tokens.put(otherClient, new Actor(TENANT_A, "other-client", Role.CLIENT));
    var server = JourneyHttpServer.start(journal, tokens,
        "no-consent".equals(args[1]) ? Set.of() : Set.of(TENANT_A + "|" + CLIENT_A));
    try {
      int port = server.port();
      if (seed) {
        var created = request(port, "POST", drafts(TENANT_A), coach, "ui01-draft",
            "{\"title\":\"Synthetic resilience\"}");
        check(created.statusCode() == 201, "fixture create");
        String path = drafts(TENANT_A) + "/" + field(created.body(), "draft_id");
        check(request(port, "PATCH", path, coach, null, updateBody(1)).statusCode() == 200, "fixture update");
        var published = request(port, "POST", path + "/publish", coach, "ui01-publish",
            "{\"expected_draft_version\":2}");
        check(published.statusCode() == 201, "fixture publish");
        System.out.println("VERSION " + field(published.body(), "journey_version_id"));
      }
      System.out.println("PORT " + port);
      System.in.read();
    } finally {
      server.stop();
    }
  }
}
