package com.projectb.api.http;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import com.projectb.api.domain.JourneyJournal;
import com.projectb.api.domain.JourneyKernel.Actor;
import com.projectb.api.domain.JourneyKernel.AssignmentView;
import com.projectb.api.domain.JourneyKernel.CanonicalPin;
import com.projectb.api.domain.JourneyKernel.DomainException;
import com.projectb.api.domain.JourneyKernel.DraftView;
import com.projectb.api.domain.JourneyKernel.ErrorCode;
import com.projectb.api.domain.JourneyKernel.PublishedView;
import com.projectb.api.domain.JourneyKernel.Role;
import com.projectb.api.domain.JourneyKernel.Step;
import com.projectb.api.json.JsonMini;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

/**
 * Local loopback journey service.
 * Bearer tokens and the consent directory are supplied by the process owner.
 * They are a development boundary, not a PIAC or KDB adapter.
 * Canonical pin fields in a draft remain untrusted fixture input.
 */
public final class JourneyHttpServer {
  private final HttpServer server;
  private final ExecutorService executor;
  private final JourneyJournal journal;
  private final Map<String, Actor> tokens;
  private final Set<String> consentedClients;

  private JourneyHttpServer(HttpServer server, ExecutorService executor, JourneyJournal journal,
                            Map<String, Actor> tokens, Set<String> consentedClients) {
    this.server = server;
    this.executor = executor;
    this.journal = journal;
    this.tokens = tokens;
    this.consentedClients = consentedClients;
  }

  public static JourneyHttpServer start(Path journalPath, Map<String, Actor> tokens,
                                        Set<String> consentedClients) throws IOException {
    JourneyJournal journal = JourneyJournal.open(journalPath);
    HttpServer server = HttpServer.create(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0), 0);
    ExecutorService executor = Executors.newFixedThreadPool(4);
    JourneyHttpServer app = new JourneyHttpServer(server, executor, journal, Map.copyOf(tokens), Set.copyOf(consentedClients));
    server.createContext("/", app::handle);
    server.setExecutor(executor);
    server.start();
    return app;
  }

  public int port() { return server.getAddress().getPort(); }

  public void stop() {
    server.stop(0);
    executor.shutdownNow();
  }

  private void handle(HttpExchange exchange) throws IOException {
    String correlation = correlation(exchange);
    try {
      route(exchange, correlation);
    } catch (DomainException ex) {
      send(exchange, status(ex.code), error(ex.code.name(), ex.getMessage(), correlation));
    } catch (IllegalArgumentException ex) {
      send(exchange, 422, error("INVALID", "request does not match the journey contract", correlation));
    } catch (RuntimeException ex) {
      send(exchange, 500, error("INTERNAL", "journey service failed closed", correlation));
    }
  }

  private void route(HttpExchange exchange, String correlation) throws IOException {
    String method = exchange.getRequestMethod();
    String[] path = exchange.getRequestURI().getPath().split("/");
    if ("GET".equals(method) && path.length == 4 && "project-b".equals(path[1])
        && "v1".equals(path[2]) && "health".equals(path[3])) {
      send(exchange, 200, "{\"data\":{\"status\":\"ready\",\"bind\":\"127.0.0.1\","
          + "\"runtime\":\"active_http\",\"piac\":\"not_connected\",\"kdb\":\"not_connected\"}}");
      return;
    }
    Actor actor = actor(exchange);
    if (actor == null) {
      send(exchange, 401, error("UNAUTHORIZED", "bearer token is required", correlation));
      return;
    }
    if (path.length < 5 || !"project-b".equals(path[1]) || !"v1".equals(path[2]) || !"tenants".equals(path[3])) {
      send(exchange, 404, error("NOT_FOUND", "route not found", correlation));
      return;
    }
    String tenant = path[4];
    if (!tenant.equals(actor.tenantId()))
      throw new DomainException(ErrorCode.FORBIDDEN, "tenant mismatch");

    if (path.length == 7 && "journeys".equals(path[5]) && "drafts".equals(path[6]) && "POST".equals(method)) {
      requireCoach(actor);
      Map<String, Object> body = body(exchange);
      DraftView view = journal.createDraft(actor, JsonMini.text(body.get("title")), idempotency(exchange));
      send(exchange, 201, draftJson(view));
      return;
    }
    if (path.length == 8 && "journeys".equals(path[5]) && "drafts".equals(path[6]) && "PATCH".equals(method)) {
      requireCoach(actor);
      Map<String, Object> body = body(exchange);
      DraftView view = journal.updateDraft(actor, UUID.fromString(path[7]),
          JsonMini.integer(body.get("expected_revision")), JsonMini.text(body.get("title")),
          steps(body.get("phases")), body.get("producer_phases") == null ? null : JsonMini.write(body.get("producer_phases")));
      send(exchange, 200, draftJson(view));
      return;
    }
    if (path.length == 9 && "journeys".equals(path[5]) && "drafts".equals(path[6])
        && "publish".equals(path[8]) && "POST".equals(method)) {
      requireCoach(actor);
      Map<String, Object> body = body(exchange);
      PublishedView view = journal.publish(actor, UUID.fromString(path[7]),
          JsonMini.integer(body.get("expected_draft_version")), idempotency(exchange));
      send(exchange, 201, versionJson(view));
      return;
    }
    if (path.length == 8 && "journeys".equals(path[5]) && "versions".equals(path[6]) && "GET".equals(method)) {
      requireCoach(actor);
      PublishedView view = journal.kernel().readPublishedForCoach(actor, UUID.fromString(path[7]));
      send(exchange, 200, versionJson(view));
      return;
    }
    if (path.length == 9 && "journeys".equals(path[5]) && "versions".equals(path[6])
        && "withdraw".equals(path[8]) && "POST".equals(method)) {
      requireCoach(actor);
      PublishedView view = journal.withdraw(actor, UUID.fromString(path[7]));
      send(exchange, 200, versionJson(view));
      return;
    }
    if (path.length == 8 && "clients".equals(path[5]) && "assignments".equals(path[7]) && "POST".equals(method)) {
      requireCoach(actor);
      String clientId = path[6];
      if (!consentedClients.contains(tenant + "|" + clientId))
        throw new DomainException(ErrorCode.CONSENT_REQUIRED, "verified client consent is required");
      Map<String, Object> body = body(exchange);
      AssignmentView view = journal.assign(actor, clientId,
          UUID.fromString(JsonMini.text(body.get("journey_version_id"))), true, idempotency(exchange));
      send(exchange, 201, assignmentJson(view));
      return;
    }
    if (path.length == 10 && "clients".equals(path[5]) && "assignments".equals(path[7])
        && "version".equals(path[9]) && "GET".equals(method)) {
      if (actor.role() != Role.CLIENT || !actor.subjectId().equals(path[6]))
        throw new DomainException(ErrorCode.FORBIDDEN, "client membership mismatch");
      PublishedView view = journal.kernel().readAssignedVersion(actor, tenant, UUID.fromString(path[8]));
      send(exchange, 200, versionJson(view));
      return;
    }
    if (path.length == 7 && "producers".equals(path[5]) && "POST".equals(method)) {
      JourneyProducer.Reply reply = JourneyProducer.handle(path[6], actor, consentedClients, journal, body(exchange));
      send(exchange, reply.status(), reply.body());
      return;
    }
    send(exchange, 404, error("NOT_FOUND", "route not found", correlation));
  }

  private static void requireCoach(Actor actor) {
    if (actor.role() != Role.COACH)
      throw new DomainException(ErrorCode.FORBIDDEN, "coach access required");
  }

  private Actor actor(HttpExchange exchange) {
    String header = exchange.getRequestHeaders().getFirst("Authorization");
    if (header == null || !header.startsWith("Bearer ")) return null;
    return tokens.get(header.substring("Bearer ".length()).trim());
  }

  private static String idempotency(HttpExchange exchange) {
    String key = exchange.getRequestHeaders().getFirst("Idempotency-Key");
    if (key == null || key.isBlank()) throw new IllegalArgumentException("idempotency key required");
    return key;
  }

  private static String correlation(HttpExchange exchange) {
    String supplied = exchange.getRequestHeaders().getFirst("X-Correlation-Id");
    if (supplied == null || supplied.isBlank()) return UUID.randomUUID().toString();
    try {
      return UUID.fromString(supplied).toString();
    } catch (IllegalArgumentException ex) {
      throw new IllegalArgumentException("correlation id must be a uuid");
    }
  }

  private static Map<String, Object> body(HttpExchange exchange) throws IOException {
    try (InputStream input = exchange.getRequestBody()) {
      byte[] bytes = input.readNBytes(1_000_000);
      if (bytes.length == 1_000_000) throw new IllegalArgumentException("body too large");
      return JsonMini.object(JsonMini.parse(new String(bytes, StandardCharsets.UTF_8)));
    }
  }

  @SuppressWarnings("unchecked")
  private static List<Step> steps(Object phasesValue) {
    if (!(phasesValue instanceof List<?> phases) || phases.isEmpty())
      throw new IllegalArgumentException("phases required");
    List<Step> steps = new ArrayList<>();
    for (Object phaseValue : phases) {
      Map<String, Object> phase = (Map<String, Object>) phaseValue;
      Object rawSteps = phase.get("steps");
      if (!(rawSteps instanceof List<?> phaseSteps)) throw new IllegalArgumentException("steps required");
      for (Object stepValue : phaseSteps) {
        Map<String, Object> step = (Map<String, Object>) stepValue;
        Object rawRefs = step.get("canonical_refs");
        if (!(rawRefs instanceof List<?> refs) || refs.isEmpty())
          throw new IllegalArgumentException("canonical ref required");
        Map<String, Object> ref = (Map<String, Object>) refs.get(0);
        Object rawAcceptance = step.get("acceptance");
        if (!(rawAcceptance instanceof Map<?, ?> acceptance))
          throw new IllegalArgumentException("fixture acceptance required");
        Map<String, Object> pin = (Map<String, Object>) acceptance;
        steps.add(new Step(JsonMini.text(step.get("step_id")), JsonMini.text(step.get("title")),
            new CanonicalPin(JsonMini.text(ref.get("ref_id")),
                             JsonMini.text(pin.get("receipt_sha256")),
                             Boolean.TRUE.equals(pin.get("approved")),
                             Boolean.TRUE.equals(pin.get("rights_granted")))));
      }
    }
    return List.copyOf(steps);
  }

  private static int status(ErrorCode code) {
    return switch (code) {
      case FORBIDDEN -> 403;
      case NOT_FOUND -> 404;
      case STALE_REVISION, IDEMPOTENCY_CONFLICT -> 409;
      case INVALID, UNPUBLISHED_CANONICAL, WITHDRAWN, CONSENT_REQUIRED -> 422;
    };
  }

  private static String error(String code, String message, String correlation) {
    return "{\"error\":{\"code\":" + JsonMini.quote(code)
        + ",\"message\":" + JsonMini.quote(message)
        + ",\"correlation_id\":" + JsonMini.quote(correlation)
        + ",\"retryable\":false}}";
  }

  private static String draftJson(DraftView view) {
    return "{\"data\":{\"draft_id\":" + JsonMini.quote(view.draftId().toString())
        + ",\"title\":" + JsonMini.quote(view.title())
        + ",\"status\":" + JsonMini.quote(view.status())
        + ",\"revision\":" + view.revision()
        + ",\"kdb_adapter\":\"not_connected\"}}";
  }

  private static String versionJson(PublishedView view) {
    return "{\"data\":{\"journey_version_id\":" + JsonMini.quote(view.journeyVersionId().toString())
        + ",\"source_draft_id\":" + JsonMini.quote(view.sourceDraftId().toString())
        + ",\"version\":" + view.version()
        + ",\"status\":" + JsonMini.quote(view.status())
        + ",\"kdb_adapter\":\"not_connected\"}}";
  }

  private static String assignmentJson(AssignmentView view) {
    return "{\"data\":{\"assignment_id\":" + JsonMini.quote(view.assignmentId().toString())
        + ",\"client_id\":" + JsonMini.quote(view.clientId())
        + ",\"journey_version_id\":" + JsonMini.quote(view.journeyVersionId().toString())
        + ",\"status\":" + JsonMini.quote(view.status())
        + ",\"piac\":\"not_connected\"}}";
  }

  private static void send(HttpExchange exchange, int status, String body) throws IOException {
    byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
    exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
    exchange.sendResponseHeaders(status, bytes.length);
    exchange.getResponseBody().write(bytes);
    exchange.close();
  }
}
