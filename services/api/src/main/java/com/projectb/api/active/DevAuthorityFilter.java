package com.projectb.api.active;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import com.projectb.api.active.KdbPublicationVerifier.KdbPinQuery;
import com.projectb.api.active.PiacDecisionConsumer.PiacQuery;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Fixture bearers and request bodies are not PIAC or KDB decisions.
 * The filter does not read the body.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class DevAuthorityFilter extends OncePerRequestFilter {
  private final PiacDecisionConsumer piac;
  private final KdbPublicationVerifier kdb;
  private final LiveAccessGate gate;

  public DevAuthorityFilter(PiacDecisionConsumer piac, KdbPublicationVerifier kdb, LiveAccessGate gate) {
    this.piac = piac;
    this.kdb = kdb;
    this.gate = gate;
  }

  @Override
  protected boolean shouldNotFilter(HttpServletRequest request) {
    String path = request.getRequestURI();
    return !path.startsWith("/project-b/");
  }

  @Override
  protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
      throws ServletException, IOException {
    String correlation = correlation(request, response);
    if (correlation == null) return;
    String header = request.getHeader("Authorization");
    if (header == null || !header.startsWith("Bearer ") || header.substring("Bearer ".length()).isBlank()) {
      write(response, 401, "UNAUTHORIZED", "bearer token is required", correlation);
      return;
    }
    String bearer = header.substring("Bearer ".length()).trim();
    String code = gate.denial(piac, kdb,
        new PiacQuery(bearer, null, "coach-delivery", correlation, false, false, false, false),
        new KdbPinQuery(null, null, null, false, false, false));
    write(response, 403, code, "live authority is closed", correlation);
  }

  private static String correlation(HttpServletRequest request, HttpServletResponse response) throws IOException {
    String supplied = request.getHeader("X-Correlation-Id");
    if (supplied == null || supplied.isBlank()) return UUID.randomUUID().toString();
    try {
      return UUID.fromString(supplied).toString();
    } catch (IllegalArgumentException ex) {
      write(response, 422, "INVALID", "correlation id must be a uuid", UUID.randomUUID().toString());
      return null;
    }
  }

  private static void write(HttpServletResponse response, int status, String code, String message, String correlation)
      throws IOException {
    response.setStatus(status);
    response.setContentType("application/json");
    response.setCharacterEncoding(StandardCharsets.UTF_8.name());
    String body = "{\"error\":{\"code\":\"" + code + "\",\"message\":\"" + message
        + "\",\"correlation_id\":\"" + correlation + "\",\"retryable\":false}}";
    response.getOutputStream().write(body.getBytes(StandardCharsets.UTF_8));
  }
}
