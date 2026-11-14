# Project B Web Shell

Local Next.js shell for the four existing routes: Public Offer, Platform Admin Provisioning, Coach Journey Builder and Client Member Home.

The standard shell uses static pages. The optional UI01 smoke enables a synthetic loopback API connection. The shell has no database, PIAC or KDB connection and uses no service-role key.

The versions in the root `package-lock.json` are the registry resolution from 2026-10-27. They are not an ARC-10 source pin and they do not admit T150.

```bash
npm ci
apps/web/scripts/renderer-smoke.sh
```

The smoke builds the shell, starts `next start` on `127.0.0.1`, checks HTTP 200 for the four routes, checks that the service-role name is absent from the build output, and stops the process.

## Arcava UI01 synthetic loopback smoke

After the strict web build, run `node apps/web/scripts/arcava-ui01-smoke.mjs`
with JDK 21+ and an installed Chromium browser. On macOS the script uses the
standard Chrome path. Set `ARCAVA_UI01_CHROME` to select another local binary.

The smoke starts an isolated journal and a prepublished PA-05 fixture, then
starts Next on `127.0.0.1` with explicit `TEST_LOOPBACK_ONLY` mode. The coach
action assigns the version through the real service. The client action uses
the returned assignment from the same browser session. Synthetic bearer values
stay within the two server processes. Outside the loopback test configuration,
both pages show their standard shell.
