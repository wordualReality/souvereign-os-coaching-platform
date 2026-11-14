package com.projectb.api.inactive;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Separately tested inactive bootstrap.
 * It does not open a socket, register product endpoints, or admit PIAC or KDB.
 */
@SpringBootApplication(scanBasePackages = "com.projectb.api.inactive")
public class InactiveBootstrap {
  public static final String ROLE = "NON_WEB_INACTIVE_BOOTSTRAP";

  public static void main(String[] args) {
    SpringApplication app = new SpringApplication(InactiveBootstrap.class);
    app.setWebApplicationType(WebApplicationType.NONE);
    app.run(args);
  }
}
