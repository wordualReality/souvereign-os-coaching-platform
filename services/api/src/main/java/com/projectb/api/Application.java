package com.projectb.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Local development HTTP process.
 * This role is the active development listener. The inactive role lives on InactiveBootstrap.
 * Protected routes stay closed until a real PIAC verifier and a real KDB verifier are connected.
 */
@SpringBootApplication(scanBasePackages = "com.projectb.api.active")
public class Application {
  public static final String ROLE = "ACTIVE_DEV_HTTP";

  public static void main(String[] args) {
    SpringApplication.run(Application.class, args);
  }
}
