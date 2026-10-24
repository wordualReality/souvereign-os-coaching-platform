package com.projectb.api;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicReference;

import org.junit.jupiter.api.Test;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.SpringApplicationRunListener;
import org.springframework.boot.WebApplicationType;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Executes Application.main and checks the inactive bootstrap contract.
 * The production main class admits a non-web context and no database bean.
 */
class ApplicationBootstrapTest {

  @Test
  void mainAdmitsInactiveNonWebBootstrap() {
    AtomicReference<SpringApplication> application = new AtomicReference<>();
    AtomicReference<ConfigurableApplicationContext> context = new AtomicReference<>();
    SpringApplication.withHook(
        candidate -> {
          application.set(candidate);
          return new SpringApplicationRunListener() {
            @Override
            public void ready(ConfigurableApplicationContext readyContext, Duration timeTaken) {
              context.set(readyContext);
            }
          };
        },
        () -> Application.main(new String[0]));
    ConfigurableApplicationContext started = context.get();
    try {
      assertThat(application.get()).isNotNull();
      assertThat(application.get().getWebApplicationType()).isEqualTo(WebApplicationType.NONE);
      assertThat(started).isInstanceOf(AnnotationConfigApplicationContext.class);
      assertThat(started.isActive()).isTrue();
      assertThat(started.getBean(Application.class)).isNotNull();
      assertThat(started.containsBean("dataSource")).isFalse();
    } finally {
      if (started != null) {
        started.close();
      }
    }
  }
}
