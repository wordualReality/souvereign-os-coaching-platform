# Arcava Backend: Local Development HTTP Lifecycle

This slice is `ARC-36/P25` step 7/10. It starts a Spring Boot 4.1.1 servlet listener for local development. The listener binds to `127.0.0.1`.

`Application.ROLE` is `ACTIVE_DEV_HTTP`. `InactiveBootstrap.ROLE` remains `NON_WEB_INACTIVE_BOOTSTRAP` and does not open a socket.

`GET /health/live` reports the process is up. `GET /health/ready` stays 503 while PIAC and KDB transports are absent. Routes under `/project-b/` deny every bearer, including local fixture tokens. Request fields such as `consent_verified`, publication pins and `runtime_session_refs` are not authority.

The journal is the existing append-only file. Denied HTTP requests do not append to it. `JourneyHttpServer` remains the separate `TEST_LOOPBACK_ONLY` fixture.

Live PIAC, live KDB, T150, T020, T050 and T160 stay not admitted. The canonical contracts are `/contracts/openapi/project-b-v1.json` and `/contracts/openapi/project-b-v1.1-overlay.json`. This listener does not replace them.

The packaged artifact starts with `com.projectb.api.Application`. `InactiveBootstrap` stays a separate non-web fixture and is not the JAR start class.

Local check: Temurin 25 and Maven 3.9.16, `mvn -B -f services/api/pom.xml package`, then `services/api/scripts/jar-lifecycle-smoke.sh services/api/target/projectb-api-0.1.0-SNAPSHOT.jar`.
