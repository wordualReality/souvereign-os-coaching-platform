package com.projectb.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Inactive Arcava backend framework bootstrap.
 * No endpoints, database, workers or providers are admitted by this main class.
 * The loopback producer listener is JourneyHttpServer and is not started here.
 */
@SpringBootApplication
public class Application {
  public static final String ROLE = "NON_WEB_INACTIVE_BOOTSTRAP";
  public static void main(String[] args) {
    SpringApplication app = new SpringApplication(Application.class);
    app.setWebApplicationType(WebApplicationType.NONE);
    app.run(args);
  }
}
