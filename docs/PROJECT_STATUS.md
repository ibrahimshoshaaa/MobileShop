# Mobile Shop ERP — Project Status

**Build:** All In One RC v3 (documentation and QA pass)
**Date:** 2026-09-17
**Scope:** Offline-first ERP/POS with optional account-linked Online mode

> This document reflects the code currently present in this build. A feature is marked **implemented** only when a corresponding module or test exists. A UI placeholder or adapter is not counted as a completed production workflow.

## 1. Product model

- **Default operating mode:** Offline-first.
- **Online activation:** Intended to be enabled from Settings by linking a company account.
- **Account model:** Tenant/company scope plus branch scope.
- **Central service:** Planned for a deployed API and Turso database; not deployed inside this archive.
- **Security principle:** Financial authority must remain on the trusted command/server boundary when Online is active.

## 2. Implemented / present in the codebase

### Backend domain and commands

- Domain models, enums, command contracts and domain errors.
- Command dispatch boundary.
- Server-side context model for user, permissions and branch access.
- Sales, purchases, stock, installments, maintenance, expenses, wallet and closing command modules.
- Transfer commission calculations and customer wallet transfer logic.
- Audit-oriented service hooks and financial validation helpers.
- Basic reporting and export modules.

### Security hardening

- HTTP command handler requires a trusted authentication verifier contract.
- Client-supplied permissions and branch claims are not accepted as authoritative.
- Branch access is checked before dispatch.
- Firestore rules are included as a starting security policy with server-write restrictions for sensitive collections.
- Security review and integration tests exist.

### Local Offline storage

- Durable SQLite repository.
- WAL mode, foreign keys, `synchronous=FULL`, and busy timeout.
- Local transaction context with rollback on exception.
- Tenant/branch-scoped command outbox.
- Idempotent `command_id` handling.
- Tenant/branch-scoped local record projection.
- Optimistic version checks and `STALE_VERSION` detection.
- Sync states: `PENDING`, `APPLIED`, `CONFLICT`, `FAILED`.
- Account-linked local profile and scope checks.

### Synchronization safeguards

- Pending command retrieval by tenant and optional branch.
- Scope mismatch is converted to a conflict instead of being executed.
- Retry attempt and error recording.
- Conflict classification for stale versions, transaction conflicts and account-scope mismatches.
- Legacy in-memory queue compatibility remains for tests/reference use.

### Applications / UI foundations

- Flutter Arabic-first navigation shell with module entries for dashboard, sales, inventory, customers, suppliers, installments, maintenance, expenses, reports, branches/users and settings.
- Desktop Tkinter POS shell with cart, checkout, return and sync action hooks.
- Hardware adapter interfaces and mock adapters.
- UI-to-command integration points are exposed as callbacks/handlers.

### Verification in this build

- `pytest`: **80 passed**.
- Python compilation check: must be rerun as part of release packaging.
- Tests cover foundation behavior, money validation, permissions, transfers, security hardening, return hardening, SQLite durability and sync hardening.

## 3. Partially implemented / requires completion

### Production database and API

- Replace in-memory ERP repositories with a complete SQL repository implementation.
- Add Turso/libSQL connection management, migrations, indexes and retry policy.
- Implement the deployed API entrypoint and real token verification.
- Make all financial commands execute atomically against the authoritative database.
- Add persistent idempotency records on the server, not only in local storage.

### Offline-to-Online behavior

- Implement authenticated upload/download protocol with cursors and server acknowledgements.
- Add durable conflict resolution workflows in the UI.
- Define per-command offline policy: allowed, queued-for-review, or blocked.
- Add server-side deduplication and ordering guarantees.
- Add reconciliation for stock, IMEI, wallet and installment conflicts.

### ERP business workflows

- Finish end-to-end persistence for sales, returns, exchanges, purchases, stock transfers and maintenance.
- Verify full accounting entries and wallet movements for every payment/refund path.
- Complete installment schedule allocation, partial collection, overdue status and rounding remainder handling.
- Complete weighted-average cost and historical cost snapshot behavior.
- Complete branch-level IMEI lifecycle and cross-branch transfer enforcement.
- Complete daily closing locks, discrepancy notes and reopening controls.
- Complete employee compensation and commission source-event linkage.

### Mobile UI

- Replace placeholder metric values with live repository/API data.
- Implement real forms, validation, loading states, empty states and error states.
- Wire every module to command/query services.
- Add barcode/IMEI scanning, product search, cart editing, split payments and receipt flow.
- Add account linking screens, secure online activation, branch selection and sync center.
- Add Arabic localization coverage and responsive layouts for phones/tablets.

### Desktop UI

- Replace demo product insertion with catalog search and barcode/IMEI lookup.
- Add real cart quantity/discount/payment editing.
- Add customer selection, credit checks, split payments and receipt printing.
- Add return/exchange workflow with original invoice validation.
- Add inventory, purchase, customer, supplier, maintenance and closing screens or connect to the shared admin UI.
- Add keyboard navigation, cashier session controls and hardware integration.

### Backup, deployment and operations

- Create the production Turso database and secure server deployment.
- Add automated encrypted backups and a tested restore procedure.
- Add environment separation for development, staging and production.
- Add monitoring, structured logs, alerting and migration rollback guidance.
- Add CI checks for tests, compilation, linting and dependency security.
- Run multi-device and multi-branch concurrency tests in a staging environment.

## 4. Explicitly not claimed as complete

- No deployed public API is included.
- No production Turso database or credentials are included.
- The Flutter screens are a navigation/UI foundation, not a complete finished mobile product.
- The desktop app is a POS shell, not a complete commercial desktop suite.
- Firebase rules are not a substitute for deploying and testing the chosen backend architecture.
- Passing the current test suite does not prove production readiness, backup recoverability, or real-device reliability.

## 5. Release acceptance checklist

Before calling the project production-ready, all of the following must be demonstrated in staging:

- [ ] Real authentication and tenant/branch authorization.
- [ ] Real Turso persistence and migrations.
- [ ] Atomic sale, return, purchase, transfer, installment and closing transactions.
- [ ] Server-side idempotency and replay tests.
- [ ] Offline queue recovery after app crash and device restart.
- [ ] Two branches attempting conflicting operations on the same IMEI/stock item.
- [ ] Complete wallet, ledger and stock reconciliation.
- [ ] Backup and restore drill with documented recovery point/objective.
- [ ] Functional mobile and desktop workflows with no placeholder actions.
- [ ] Security review of deployed API and database policies.
- [ ] Automated test, build and packaging pipeline.

## 6. Recommended implementation order

1. Authoritative SQL schema, migrations and repository layer.
2. Deployed API with authentication, authorization and idempotency.
3. Complete transactional ERP services and reconciliation tests.
4. Offline sync protocol and conflict-resolution screens.
5. Functional desktop POS workflows.
6. Functional mobile administration workflows.
7. Backup/restore, observability, staging tests and release packaging.
