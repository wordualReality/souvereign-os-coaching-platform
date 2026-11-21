package com.projectb.api.http;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import com.projectb.api.domain.C19LocalReview;
import com.projectb.api.domain.GoalProposalAdapter;
import com.projectb.api.domain.GoalProposalAdapter.AdapterFailure;
import com.projectb.api.domain.GoalProposalAdapter.ProposedStep;
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

  public static final String LOOPBACK_PROFILE = "TEST_LOOPBACK_ONLY";

  public static JourneyHttpServer start(Path journalPath, Map<String, Actor> tokens,
                                        Set<String> consentedClients) throws IOException {
    return start(JourneyJournal.open(journalPath), tokens, consentedClients);
  }

  public static JourneyHttpServer start(JourneyJournal journal, Map<String, Actor> tokens,
                                        Set<String> consentedClients) throws IOException {
    HttpServer server = HttpServer.create(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0), 0);
    ExecutorService executor = Executors.newFixedThreadPool(4);
    JourneyHttpServer app = new JourneyHttpServer(server, executor, journal, Map.copyOf(tokens), Set.copyOf(consentedClients));
    server.createContext("/", app::handle);
    server.setExecutor(executor);
    server.start();
    return app;
  }

  public static JourneyHttpServer startLive(Path journalPath, TrustedPiacVerifier piac, TrustedKdbVerifier kdb) {
    if (journalPath == null || piac == null || kdb == null
        || !piac.verifiesLiveIdentity() || !kdb.verifiesLivePublication())
      throw new IllegalStateException("live runtime closed without verified PIAC and KDB authorities");
    throw new IllegalStateException("live listener is not admitted in this repair");
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
      send(exchange, status(ex.code), error(ex.code.name(), ex.getMessage(), correlation, false));
    } catch (AdapterFailure ex) {
      send(exchange, 503, error("ADAPTER_UNAVAILABLE", ex.getMessage(), correlation, true));
    } catch (IllegalArgumentException ex) {
      send(exchange, 422, error("INVALID", "request does not match the journey contract", correlation, false));
    } catch (IOException ex) {
      send(exchange, 503, error("PERSISTENCE_FAILED", "journal commit failed closed", correlation, false));
    } catch (RuntimeException ex) {
      send(exchange, 500, error("INTERNAL", "journey service failed closed", correlation, false));
    }
  }

  private void route(HttpExchange exchange, String correlation) throws IOException {
    String method = exchange.getRequestMethod();
    String[] path = exchange.getRequestURI().getPath().split("/");
    if ("GET".equals(method) && path.length == 4 && "project-b".equals(path[1])
        && "v1".equals(path[2]) && "health".equals(path[3])) {
      send(exchange, 200, "{\"data\":{\"status\":\"ready\",\"bind\":\"127.0.0.1\","
          + "\"profile\":\"" + LOOPBACK_PROFILE + "\",\"runtime\":\"loopback_fixture\","
          + "\"piac\":\"not_connected\",\"kdb\":\"not_connected\"}}");
      return;
    }
    Actor actor = actor(exchange);
    if (actor == null) {
      send(exchange, 401, error("UNAUTHORIZED", "bearer token is required", correlation, false));
      return;
    }
    if (path.length < 5 || !"project-b".equals(path[1]) || !"v1".equals(path[2]) || !"tenants".equals(path[3])) {
      send(exchange, 404, error("NOT_FOUND", "route not found", correlation, false));
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
    if (path.length == 8 && "journeys".equals(path[5]) && "drafts".equals(path[6]) && "GET".equals(method)) {
      requireCoach(actor);
      DraftView view = journal.kernel().readDraft(actor, UUID.fromString(path[7]));
      send(exchange, 200, draftDetailJson(actor, view));
      return;
    }
    if (path.length == 7 && "journeys".equals(path[5]) && "draft-proposals".equals(path[6]) && "POST".equals(method)) {
      requireCoach(actor);
      send(exchange, 200, JsonMini.write(Map.of("data", propose(body(exchange)))));
      return;
    }
    if (path.length == 8 && "journeys".equals(path[5]) && "draft-proposals".equals(path[6])
        && "commit".equals(path[7]) && "POST".equals(method)) {
      requireCoach(actor);
      send(exchange, 201, commitProposal(actor, body(exchange), idempotency(exchange)));
      return;
    }
    if (path.length == 9 && "journeys".equals(path[5]) && "drafts".equals(path[6])
        && "local-review".equals(path[8]) && "POST".equals(method)) {
      requireCoach(actor);
      send(exchange, 201, localReview(actor, UUID.fromString(path[7]), body(exchange), idempotency(exchange)));
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
    if (path.length == 12 && "clients".equals(path[5]) && "assignments".equals(path[7])
        && "version".equals(path[9]) && "steps".equals(path[10]) && "GET".equals(method)) {
      if (actor.role() != Role.CLIENT || !actor.subjectId().equals(path[6]))
        throw new DomainException(ErrorCode.FORBIDDEN, "client membership mismatch");
      if (exchange.getRequestURI().getRawQuery() != null)
        throw new IllegalArgumentException("step open uses only the stored source reference");
      send(exchange, 200, assignedStep(actor, tenant, UUID.fromString(path[8]), path[11]));
      return;
    }
    if (path.length == 14 && "clients".equals(path[5]) && "assignments".equals(path[7])
        && "versions".equals(path[9]) && "steps".equals(path[11]) && "messages".equals(path[13])
        && ("GET".equals(method) || "POST".equals(method))) {
      if (exchange.getRequestURI().getRawQuery() != null)
        throw new IllegalArgumentException("query override denied");
      String client = path[6];
      synchronized (journal) {
        var scope = journal.messageScope(actor, client, UUID.fromString(path[8]),
            UUID.fromString(path[10]), path[12]);
        if (!consentedClients.contains(tenant + "|" + client))
          throw new DomainException(ErrorCode.CONSENT_REQUIRED, "current fixture consent required");
        Map<String, Object> data = new java.util.LinkedHashMap<>(Map.of(
            "assignment_id", scope.assignmentId().toString(), "journey_version_id", scope.versionId().toString(),
            "step_id", scope.stepId(), "source_ref", journal.pa05Source(), "profile", LOOPBACK_PROFILE));
        boolean posting = "POST".equals(method);
        if (posting) {
          Map<String, Object> payload = body(exchange);
          if (!payload.keySet().equals(Set.of("body"))) throw new IllegalArgumentException("body field required");
          data.put("message", messageJson(journal.sendStepMessage(actor, scope,
              JsonMini.text(payload.get("body")), idempotency(exchange))));
        } else {
          data.put("messages", journal.stepMessages(actor, scope).stream().map(JourneyHttpServer::messageJson).toList());
        }
        send(exchange, posting ? 201 : 200, JsonMini.write(Map.of("data", data)));
      }
      return;
    }
    if (path.length == 15 && "clients".equals(path[5]) && "assignments".equals(path[7])
        && "versions".equals(path[9]) && "steps".equals(path[11]) && "progress".equals(path[13])) {
      progress(exchange, actor, path);
      return;
    }
    if (path.length == 14 && "clients".equals(path[5]) && "assignments".equals(path[7])
        && "versions".equals(path[9]) && "steps".equals(path[11]) && "media-links".equals(path[13])
        && ("GET".equals(method) || "POST".equals(method))) {
      media(exchange, actor, path, false);
      return;
    }
    if (path.length == 15 && "clients".equals(path[5]) && "assignments".equals(path[7])
        && "versions".equals(path[9]) && "steps".equals(path[11]) && "media-links".equals(path[13])
        && "withdraw".equals(path[14]) && "POST".equals(method)) {
      media(exchange, actor, path, true);
      return;
    }
    if (path.length == 7 && "producers".equals(path[5]) && "POST".equals(method)) {
      JourneyProducer.Reply reply = JourneyProducer.handle(path[6], actor, consentedClients, journal, body(exchange));
      send(exchange, reply.status(), reply.body());
      return;
    }
    send(exchange, 404, error("NOT_FOUND", "route not found", correlation, false));
  }

  private void progress(HttpExchange exchange, Actor actor, String[] path) throws IOException {
    String operation = path[14];
    String method = exchange.getRequestMethod();
    boolean reading = "GET".equals(method) && ("own".equals(operation) || "released".equals(operation));
    boolean writing = "POST".equals(method) && Set.of("complete", "share", "revoke").contains(operation);
    if (!reading && !writing) {
      send(exchange, 404, error("NOT_FOUND", "progress route not found", correlation(exchange), false));
      return;
    }
    if (exchange.getRequestURI().getRawQuery() != null)
      throw new IllegalArgumentException("query override denied");
    boolean coachRead = "released".equals(operation);
    if (actor.role() != (coachRead ? Role.COACH : Role.CLIENT))
      throw new DomainException(ErrorCode.FORBIDDEN, "progress role required");
    Map<String, Object> payload = writing ? body(exchange) : Map.of();
    synchronized (journal) {
      var scope = journal.messageScope(actor, path[6], UUID.fromString(path[8]),
          UUID.fromString(path[10]), path[12]);
      if (!consentedClients.contains(scope.tenantId() + "|" + scope.clientId()))
        throw new DomainException(ErrorCode.CONSENT_REQUIRED, "current fixture consent required");
      Map<String, Object> result = new java.util.LinkedHashMap<>(Map.of(
          "assignment_id", scope.assignmentId().toString(), "journey_version_id", scope.versionId().toString(),
          "step_id", scope.stepId()));
      if (coachRead) {
        if (!journal.releasedProgress(actor, scope))
          throw new DomainException(ErrorCode.NOT_FOUND, "released progress unavailable");
        result.put("step_completed", true);
      } else {
        if (writing) {
          var action = JourneyJournal.ProgressAction.valueOf(operation.toUpperCase(java.util.Locale.ROOT));
          var event = journal.changeProgress(actor, scope, action, idempotency(exchange), payload.isEmpty());
          result.put("event_id", event.id().toString());
        }
        var state = journal.clientProgress(actor, scope);
        result.put("tenant_id", scope.tenantId());
        result.put("client_id", scope.clientId());
        result.put("source_ref", journal.pa05Source());
        result.put("step_completed", state != null);
        result.put("visibility", state != null && state.releaseId() != null ? "RELEASED" : "PRIVATE");
        if (state != null) result.put("completion_id", state.completionId().toString());
        if (state != null && state.releaseId() != null) result.put("release_id", state.releaseId().toString());
      }
      send(exchange, writing ? 201 : 200, JsonMini.write(Map.of("data", result)));
    }
  }

  private void media(HttpExchange exchange, Actor actor, String[] path, boolean withdraw) throws IOException {
    if (exchange.getRequestURI().getRawQuery() != null)
      throw new IllegalArgumentException("query override denied");
    boolean posting = "POST".equals(exchange.getRequestMethod());
    if (posting && actor.role() != Role.COACH)
      throw new DomainException(ErrorCode.FORBIDDEN, "coach media access required");
    Map<String, Object> payload = posting ? body(exchange) : Map.of();
    synchronized (journal) {
      var scope = journal.messageScope(actor, path[6], UUID.fromString(path[8]),
          UUID.fromString(path[10]), path[12]);
      if (!consentedClients.contains(scope.tenantId() + "|" + scope.clientId()))
        throw new DomainException(ErrorCode.CONSENT_REQUIRED, "current fixture consent required");
      Map<String, Object> data = new LinkedHashMap<>();
      data.put("assignment_id", scope.assignmentId().toString());
      data.put("journey_version_id", scope.versionId().toString());
      data.put("step_id", scope.stepId());
      data.put("source_ref", journal.pa05Source());
      data.put("profile", LOOPBACK_PROFILE);
      JourneyJournal.MediaLink link;
      if (withdraw) {
        if (!payload.isEmpty()) throw new IllegalArgumentException("media withdraw takes an empty object");
        link = journal.withdrawMediaLink(actor, scope, idempotency(exchange));
      } else if (posting) {
        if (!payload.keySet().equals(Set.of("url", "title")))
          throw new IllegalArgumentException("url and title required");
        link = journal.attachMediaLink(actor, scope, JsonMini.text(payload.get("url")),
            JsonMini.text(payload.get("title")), idempotency(exchange));
      } else {
        link = journal.activeMediaLink(actor, scope);
      }
      data.put("media_link", mediaJson(link));
      send(exchange, posting ? 201 : 200, JsonMini.write(Map.of("data", data)));
    }
  }

  private static Map<String, Object> mediaJson(JourneyJournal.MediaLink link) {
    Map<String, Object> media = new LinkedHashMap<>();
    media.put("media_link_id", link.mediaLinkId().toString());
    media.put("link_version", link.linkVersion());
    media.put("owner_id", link.ownerId());
    media.put("url", link.url());
    media.put("title", link.title());
    media.put("rights_state", JourneyJournal.MEDIA_RIGHTS);
    media.put("use", JourneyJournal.MEDIA_USE);
    media.put("visibility", link.withdrawn() ? "WITHDRAWN" : "ACTIVE");
    return media;
  }

  private String assignedStep(Actor actor, String tenant, UUID assignment, String stepId) {
    synchronized (journal) {
      PublishedView version = journal.kernel().readAssignedVersion(actor, tenant, assignment);
      Step step = journal.pa05Step(version, stepId);
      return JsonMini.write(Map.of("data", Map.of(
          "journey_version_id", version.journeyVersionId().toString(), "step_id", step.stepId(),
          "title", step.title(), "source_ref", journal.pa05Source(), "profile", LOOPBACK_PROFILE)));
    }
  }

  private static Map<String, Object> messageJson(JourneyJournal.StepMessage message) {
    return Map.of("message_id", message.id().toString(), "sender_role", message.sender().role().name(),
        "sender_id", message.sender().subjectId(), "body", message.body());
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

  private static Map<String, Object> propose(Map<String, Object> body) {
    boolean forceError = Boolean.TRUE.equals(body.get("force_adapter_error"));
    List<String> candidateIds = strings(body.get("candidate_ids"));
    return new GoalProposalAdapter().json(new GoalProposalAdapter()
        .propose(JsonMini.text(body.get("learning_goal")), candidateIds, forceError));
  }

  private String commitProposal(Actor actor, Map<String, Object> body, String key) throws IOException {
    GoalProposalAdapter adapter = new GoalProposalAdapter();
    if (Boolean.TRUE.equals(body.get("force_adapter_error")))
      throw new AdapterFailure("synthetic proposal adapter unavailable");
    List<ProposedStep> edited = adapter.parseEdited(body.get("steps"));
    List<Step> kernelSteps = adapter.kernelSteps(edited);
    String title = JsonMini.text(body.get("title"));
    String phases = adapter.phasesJson(edited);
    DraftView view;
    Object draftIdValue = body.get("draft_id");
    if (draftIdValue == null) {
      view = journal.createDraft(actor, title, key, C19LocalReview.ORIGIN);
      DraftView current = journal.kernel().readDraft(actor, view.draftId());
      if (current.steps().isEmpty())
        view = journal.updateDraft(actor, current.draftId(), current.revision(), title, kernelSteps, phases,
            C19LocalReview.ORIGIN);
      else view = current;
    } else {
      view = journal.updateDraft(actor, UUID.fromString(JsonMini.text(draftIdValue)),
          JsonMini.integer(body.get("expected_revision")), title, kernelSteps, phases, C19LocalReview.ORIGIN);
    }
    Map<String, Object> data = new LinkedHashMap<>();
    data.put("draft_id", view.draftId().toString());
    data.put("title", view.title());
    data.put("status", view.status());
    data.put("revision", view.revision());
    data.put("profile", GoalProposalAdapter.PROFILE);
    data.put("proposal_kind", GoalProposalAdapter.PROPOSAL_KIND);
    data.put("publication_state", "DRAFT");
    data.put("test_only", true);
    data.put("no_live_kdb", true);
    data.put("kdb_adapter", "not_connected");
    data.put("steps", edited.stream().map(adapter::stepJsonMap).toList());
    attachReview(actor, view, data);
    return JsonMini.write(Map.of("data", data));
  }

  private String localReview(Actor actor, UUID pathDraftId, Map<String, Object> body, String key)
      throws IOException {
    if (body.containsKey("digest") || body.containsKey("reviewer_id") || body.containsKey("tenant_id"))
      throw new IllegalArgumentException("client digest and actor fields are not accepted");
    if (body.containsKey("key") && !key.equals(JsonMini.text(body.get("key"))))
      throw new IllegalArgumentException("idempotency key mismatch");
    java.util.HashSet<String> allowed = new java.util.HashSet<>(Set.of("draft_id", "expected_revision"));
    if (body.containsKey("key")) allowed.add("key");
    if (!body.keySet().equals(allowed))
      throw new IllegalArgumentException("unknown local-review field");
    UUID draftId = UUID.fromString(JsonMini.text(body.get("draft_id")));
    if (!pathDraftId.equals(draftId))
      throw new DomainException(ErrorCode.INVALID, "draft id mismatch");
    C19LocalReview.Receipt receipt = journal.localReview(actor, draftId,
        JsonMini.integer(body.get("expected_revision")), key);
    DraftView view = journal.kernel().readDraft(actor, draftId);
    Map<String, Object> data = new LinkedHashMap<>();
    data.put("draft_id", view.draftId().toString());
    data.put("title", view.title());
    data.put("status", view.status());
    data.put("revision", view.revision());
    data.put("publication_state", "DRAFT");
    data.put("test_only", true);
    data.put("no_live_kdb", true);
    attachReview(actor, view, data);
    data.put("review_receipt", receiptMap(receipt));
    return JsonMini.write(Map.of("data", data));
  }

  @SuppressWarnings("unchecked")
  private static List<String> strings(Object value) {
    if (!(value instanceof List<?> list)) throw new IllegalArgumentException("candidate ids required");
    List<String> ids = new ArrayList<>();
    for (Object item : list) ids.add(JsonMini.text(item));
    return ids;
  }

  private String draftDetailJson(Actor actor, DraftView view) {
    GoalProposalAdapter adapter = new GoalProposalAdapter();
    List<Map<String, Object>> steps = new ArrayList<>();
    for (Step step : view.steps()) steps.add(adapter.sourcedKernelStep(step));
    Map<String, Object> data = new LinkedHashMap<>();
    data.put("draft_id", view.draftId().toString());
    data.put("title", view.title());
    data.put("status", view.status());
    data.put("revision", view.revision());
    data.put("kdb_adapter", "not_connected");
    data.put("profile", LOOPBACK_PROFILE);
    data.put("proposal_kind", GoalProposalAdapter.PROPOSAL_KIND);
    data.put("publication_state", "DRAFT");
    data.put("test_only", true);
    data.put("no_live_kdb", true);
    data.put("steps", steps);
    attachReview(actor, view, data);
    return JsonMini.write(Map.of("data", data));
  }

  private void attachReview(Actor actor, DraftView view, Map<String, Object> data) {
    String origin = journal.originOf(view.draftId());
    if (origin != null) data.put("origin", origin);
    if (!C19LocalReview.ORIGIN.equals(origin) || view.steps().isEmpty()) {
      data.put("review_state", C19LocalReview.STATE_NONE);
      return;
    }
    data.put("digest", C19LocalReview.digest(view));
    String state = journal.reviewState(actor, view.draftId());
    data.put("review_state", state);
    data.put("review_label", "LOCAL TEST REVIEW, NOT PUBLISHING");
    C19LocalReview.Receipt current = journal.currentReview(actor, view.draftId());
    if (current != null) data.put("review_receipt", receiptMap(current));
  }

  private static Map<String, Object> receiptMap(C19LocalReview.Receipt receipt) {
    Map<String, Object> json = new LinkedHashMap<>();
    json.put("draft_id", receipt.draftId().toString());
    json.put("revision", receipt.revision());
    json.put("digest", receipt.digest());
    json.put("reviewer_id", receipt.reviewerId());
    json.put("tenant_id", receipt.tenantId());
    json.put("test_only", receipt.testOnly());
    json.put("review_state", C19LocalReview.STATE_ACCEPTED);
    json.put("publication_state", "DRAFT");
    return json;
  }

  private static String error(String code, String message, String correlation, boolean retryable) {
    return "{\"error\":{\"code\":" + JsonMini.quote(code)
        + ",\"message\":" + JsonMini.quote(message)
        + ",\"correlation_id\":" + JsonMini.quote(correlation)
        + ",\"retryable\":" + retryable + "}}";
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
