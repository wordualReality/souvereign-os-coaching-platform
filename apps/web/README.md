# Project B Web Shell

Local Next.js shell for the four existing routes: Public Offer, Platform Admin Provisioning, Coach Journey Builder and Client Member Home.

The pages stay static. This process does not call the API, a database, PIAC or KDB. It does not read a service-role key.

The versions in the root `package-lock.json` are the registry resolution from 2026-10-27. They are not an ARC-10 source pin and they do not admit T150.

```bash
npm ci
apps/web/scripts/renderer-smoke.sh
```

The smoke builds the shell, starts `next start` on `127.0.0.1`, checks HTTP 200 for the four routes, checks that the service-role name is absent from the build output, and stops the process.
