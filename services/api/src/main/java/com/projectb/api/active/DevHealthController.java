package com.projectb.api.active;

import java.util.LinkedHashMap;
import java.util.Map;
import com.projectb.api.Application;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class DevHealthController {
  private final PiacDecisionConsumer piac;
  private final KdbPublicationVerifier kdb;
  private final LiveAccessGate gate;

  public DevHealthController(PiacDecisionConsumer piac, KdbPublicationVerifier kdb, LiveAccessGate gate) {
    this.piac = piac;
    this.kdb = kdb;
    this.gate = gate;
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
