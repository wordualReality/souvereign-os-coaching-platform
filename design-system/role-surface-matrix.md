# Role-Surface Matrix

Date: 2026-07-01

| Surface | PLATFORM_ADMIN | TENANT_ADMIN | COACH | CLIENT | SUPPORT_OPS |
|---|---|---|---|---|---|
| Tenant Creation | YES | NO | NO | NO | READ |
| Client Creation | YES | YES | NO | NO | READ |
| Client-Tenant Assignment | YES | YES | NO | NO | READ |
| Coach Assignment | YES | YES | SELF | NO | READ |
| Provisioning Status | YES | YES | READ | NO | READ |
| Invite Management | YES | YES | NO | NO | READ |
| Audit Log | YES | READ | NO | NO | READ |
| Protocol Content | NO | NO | NO | NO | NO |

All access enforced by RLS at database layer.
