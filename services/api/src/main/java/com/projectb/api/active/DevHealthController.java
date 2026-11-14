package com.projectb.api.active;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.LinkedHashMap;
import java.util.Map;
import com.projectb.api.Application;
import org.springframework.core.env.Environment;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class DevHealthController {
  private final PiacDecisionConsumer piac;
  private final KdbPublicationVerifier kdb;
  private final LiveAccessGate gate;
  private final Environment environment;

  public DevHealthController(PiacDecisionConsumer piac, KdbPublicationVerifier kdb, LiveAccessGate gate,
      Environment environment) {
    this.piac = piac;
    this.kdb = kdb;
    this.gate = gate;
    this.environment = environment;
  }

  @GetMapping("/health/live")
  Map<String, Object> live() {
    return body("up");
  }

  @GetMapping("/health/ready")
  ResponseEntity<Map<String, Object>> ready() {
    boolean ready = gate.protectedTrafficReady(piac, kdb);
    return ResponseEntity.status(ready ? 200 : 503).body(body(ready ? "ready" : "closed"));
  }

  @GetMapping("/health/effective")
  Map<String, Object> effective() {
    String journal = environment.getProperty("arcava.journal.path", "");
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("SERVER_ADDRESS", environment.getProperty("server.address", ""));
    body.put("SERVER_PORT", Integer.valueOf(environment.getProperty("local.server.port", "0")));
    body.put("ARCAVA_RUNTIME_ROLE", environment.getProperty("arcava.runtime.role", ""));
    String profile = environment.getProperty("spring.profiles.active", "");
    if (!profile.isBlank()) body.put("SPRING_PROFILES_ACTIVE", profile);
    body.put("ARCAVA_JOURNAL_PATH_PRESENT", !journal.isBlank());
    body.put("ARCAVA_JOURNAL_PATH_SHA256", sha256(journal));
    boolean transport = gate.protectedTrafficReady(piac, kdb);
    body.put("piac_transport", piac.admitsLiveTransport() ? "open" : "not_connected");
    body.put("kdb_transport", kdb.admitsLiveTransport() ? "open" : "not_connected");
    body.put("e1_authority", "NOT_ADMITTED");
    body.put("e1_reason", transport ? "LIVE_ADAPTER_NOT_ADMITTED" : "LIVE_AUTHORITY_CLOSED");
    return body;
  }

  private static String sha256(String value) {
    try {
      byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
      StringBuilder hex = new StringBuilder(digest.length * 2);
      for (byte b : digest) hex.append(String.format("%02x", b));
      return hex.toString();
    } catch (Exception ex) {
      throw new IllegalStateException("sha256 unavailable");
    }
  }

  private static Map<String, Object> body(String status) {
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("status", status);
    body.put("role", Application.ROLE);
    body.put("operator_classification", "ACTIVE_HTTP_LISTENER");
    body.put("bind", "127.0.0.1");
    body.put("profile", "DEV_LOCAL");
    body.put("piac", "not_connected");
    body.put("kdb", "not_connected");
    body.put("live_authority", "closed");
    return body;
  }
}
