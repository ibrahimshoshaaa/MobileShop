# Mobile Shop ERP — RC v3 Master Tracking

> **Historical / superseded tracking document.**
> Canonical tracking is now `Mobile_Shop_ERP_Master_Tracking.md` at the repository root.
> The RC3 status below is retained for history and must not be used as the current release gate.

## Completed in this hardening pass

### Security / Identity
- [x] Added `tenant_id` to `CommandContext`.
- [x] Added tenant-scoped idempotency key: `tenant_id:command_id`.
- [x] Scoped audit record keys to tenant.
- [x] HTTP boundary propagates trusted tenant identity.
- [x] Added Firebase production authentication boundary.
- [x] Added explicit production/dev auth provider selection.
- [x] Added startup guard refusing production with dev-token authentication.
- [x] Kept dev auth available for development/tests only.

### ERP validation
- [x] Supplier reference validation for purchase/payment flows.
- [x] Supplier branch-access validation where branch ownership is defined.
- [x] Customer reference validation for sales/collections/maintenance flows.
- [x] Added regression coverage for tenant-scoped idempotency.

### Persistence
- [x] Wrapped durable SQLite transaction flow in a DB transaction.
- [x] Roll back DB and in-memory state together when persistence fails.
- [x] Persist deletions correctly.
- [x] Persist processed/idempotency deletions correctly.

### CI / DevOps
- [x] Added GitHub Actions CI.
- [x] Python compile check.
- [x] Automated pytest run.
- [x] Bandit security scan.
- [x] pip-audit dependency scan.
- [x] Added Dependabot configuration.
- [x] Added production release gates documentation.
- [x] Added security policy and environment example.

### Verification
- [x] Latest CI run passed.
- [x] Python compile passed.
- [x] Test suite passed: **102 tests**.
- [x] Bandit passed.
- [x] pip-audit passed.

## Still required before production release

### P0 — Data isolation / persistence
- [ ] Add tenant ownership to every tenant-owned domain entity and persisted record.
- [ ] Enforce tenant filtering in repositories and queries, not only command context.
- [ ] Add cross-tenant negative tests for every sensitive entity.
- [ ] Implement and verify managed Turso/libSQL production adapter.
- [ ] Make SQL the authoritative source of truth.
- [ ] Verify transaction behavior under DB/network failure.
- [ ] Implement backup and restore drill.

### P0 — Authentication / authorization
- [ ] Complete Firebase/OIDC production configuration.
- [ ] Store branch membership and permissions in trusted server-side authorization data.
- [ ] Ensure request body cannot override tenant, user, branch, or permissions.
- [ ] Add token revocation / expiry integration tests.
- [ ] Add authorization tests for every command.

### P0 — API
- [ ] Complete authenticated query endpoints.
- [ ] Complete command endpoints.
- [ ] Apply tenant + branch + permission checks to every endpoint.
- [ ] Add consistent public error contract.
- [ ] Add request schema validation.

### P0 — Offline sync
- [ ] Server upload endpoint.
- [ ] Download cursor/version protocol.
- [ ] Conflict reconciliation.
- [ ] Retry/backoff.
- [ ] Multi-device concurrency tests.
- [ ] Reconciliation audit trail.

### P1 — ERP correctness
- [ ] Full sales/returns/refunds accounting matrix.
- [ ] Purchases/payment matrix.
- [ ] Wallet/ledger invariants.
- [ ] Installment lifecycle.
- [ ] IMEI lifecycle.
- [ ] Branch transfer lifecycle.
- [ ] Day closing.
- [ ] Concurrency/duplicate-command tests.

### P1 — Clients
- [ ] Remove demo/hard-coded dashboard values.
- [ ] Connect all mobile workflows to authenticated API.
- [ ] Connect desktop workflows to the same server API.
- [ ] Expose online/offline/sync state.
- [ ] Complete remaining placeholder pages.

### P2 — Hardware / Release
- [ ] Barcode scanner integration.
- [ ] Thermal printer integration.
- [ ] Cash drawer integration where required.
- [ ] Staging smoke test.
- [ ] Production smoke test.
- [ ] Build/release artifacts verification.
- [ ] Final backup/restore verification.

## Historical release rule

Do **not** merge `production-hardening/rc3` into `main` until all P0 items are verified and the staging smoke test passes.
