package com.projectb.api;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicReference;

import org.junit.jupiter.api.Test;
import com.projectb.api.http.JourneyHttpServer;
import com.projectb.api.http.TrustedKdbVerifier;
import com.projectb.api.http.TrustedPiacVerifier;
import com.projectb.api.inactive.InactiveBootstrap;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.SpringApplicationRunListener;
import org.springframework.boot.WebApplicationType;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The inactive bootstrap stays non-web.
 * Application.main is the separate active development listener.
 */
class ApplicationBootstrapTest {

  @Test
  void inactiveBootstrapStaysNonWeb() {
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
        () -> InactiveBootstrap.main(new String[0]));
    ConfigurableApplicationContext started = context.get();
    try {
      assertThat(application.get()).isNotNull();
      assertThat(application.get().getWebApplicationType()).isEqualTo(WebApplicationType.NONE);
      assertThat(started).isInstanceOf(AnnotationConfigApplicationContext.class);
      assertThat(started.isActive()).isTrue();
      assertThat(started.getBean(InactiveBootstrap.class)).isNotNull();
      assertThat(started.containsBean("dataSource")).isFalse();
      assertThat(started.containsBean("journeyHttpServer")).isFalse();
      assertThat(InactiveBootstrap.ROLE).isEqualTo("NON_WEB_INACTIVE_BOOTSTRAP");
    } finally {
      if (started != null) {
        started.close();
      }
    }
  }

  @Test
  void liveProfileStaysClosedWithoutVerifiedAuthorities() throws Exception {
    Path journal = Files.createTempDirectory("arcava-live-maven").resolve("journal.ndjson");
    assertThatThrownBy(() -> JourneyHttpServer.startLive(journal, TrustedPiacVerifier.NONE, TrustedKdbVerifier.NONE))
        .isInstanceOf(IllegalStateException.class)
        .hasMessageContaining("live runtime closed");
    assertThat(InactiveBootstrap.ROLE).isEqualTo("NON_WEB_INACTIVE_BOOTSTRAP");
    assertThat(Application.ROLE).isEqualTo("ACTIVE_DEV_HTTP");
    assertThat(Files.exists(journal)).isFalse();
  }
}
