package com.projectb.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Inactive Arcava backend framework bootstrap.
 * No endpoints, database, workers or providers are admitted by this main class.
 */
@SpringBootApplication
public class Application {
  public static void main(String[] args) {
    SpringApplication app = new SpringApplication(Application.class);
    app.setWebApplicationType(WebApplicationType.NONE);
    app.run(args);
  }
}
