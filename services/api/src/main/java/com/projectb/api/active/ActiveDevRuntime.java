package com.projectb.api.active;

import java.net.InetAddress;
import java.nio.file.Path;
import com.projectb.api.domain.JourneyJournal;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.tomcat.servlet.TomcatServletWebServerFactory;
import org.springframework.boot.web.server.WebServerFactoryCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;

@Configuration
public class ActiveDevRuntime {
  @Bean
  JourneyJournal journeyJournal(@Value("${arcava.journal.path}") String configured) throws Exception {
    if (configured == null || configured.isBlank())
      throw new IllegalStateException("arcava.journal.path is required");
    return JourneyJournal.open(Path.of(configured));
  }

  @Bean
  PiacDecisionConsumer piacDecisionConsumer() { return new DenyByDefaultPiacConsumer(); }

  @Bean
  KdbPublicationVerifier kdbPublicationVerifier() { return new DenyByDefaultKdbPublicationVerifier(); }

  @Bean
  LiveAccessGate liveAccessGate() { return new LiveAccessGate(); }

  @Bean
  WebServerFactoryCustomizer<TomcatServletWebServerFactory> loopbackBind(Environment environment) {
    return factory -> {
      String configured = environment.getProperty("server.address", "");
      boolean configuredLoopback = "127.0.0.1".equals(configured) || "localhost".equals(configured) || "::1".equals(configured);
      InetAddress address = factory.getAddress();
      if (!configuredLoopback || (address != null && !address.isLoopbackAddress()))
        throw new IllegalStateException("active dev runtime refuses a non-loopback bind");
    };
  }
}
