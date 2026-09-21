# Production Release Plan

This branch is the production-hardening track for RC v3.

## Gate 1 — Security
- Real identity verification (Firebase ID token or another OIDC provider).
- Tenant ID derived only from trusted server-side claims.
- Branch access derived from trusted claims/authorization data.
- No development tokens in production.
- Idempotency must be scoped to tenant + command ID and reject a reused ID with a different request payload.
- Secrets are environment/deployment settings only.

## Gate 2 — Persistence
- One authoritative SQL database.
- A single transaction must cover domain writes, ledger/stock/wallet/audit and idempotency.
- Persistence failure must roll back both SQL and in-memory state.
- Managed Turso/libSQL is the target production adapter; local SQLite remains a development adapter.

## Gate 3 — API
- Separate authenticated read/query endpoints from command writes.
- Every endpoint enforces tenant, branch and permission scope.
- Never accept permissions/tenant identity from the request body.

## Gate 4 — Sync
- Offline commands carry stable IDs.
- Server is idempotent.
- Sync protocol has cursor/versioning, conflict states, retry and reconciliation.
- Multi-device concurrency tests are required.

## Gate 5 — ERP correctness
Required test matrix:
- cash/credit/partial sales
- discounts
- returns/refunds/exchanges
- purchases/payments
- wallet transfers and commissions
- installments
- IMEI lifecycle
- stock transfers
- day closing
- accounting invariants

## Gate 6 — Clients
- Mobile dashboard and all workflows use real API data.
- Desktop online workflows use the same API.
- Offline state and sync status are visible.
- Remove demo/hard-coded production values.

## Gate 7 — Release
- CI green.
- Dependency/security audit green.
- Build artifacts reproducible.
- Backup/restore verified.
- Staging smoke test passes.
- Production secrets configured.
- Only then merge/release.

## Current branch policy

No direct merge to main until the gates above are explicitly verified.
main is the protected release line; this branch is allowed to fail while hardening is in progress.
