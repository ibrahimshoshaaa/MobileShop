# Production Release Gates

This checklist is intentionally evidence-based. A green unit-test CI run is not, by itself, a production approval.

## Gate 1 — CI and security
- Backend tests and compile checks.
- Bandit and pip-audit.
- Flutter admin/mobile analysis.
- Python desktop/POS compile checks.

## Gate 2 — Staging
Workflow: `.github/workflows/staging-smoke.yml`

Required GitHub Actions secrets:
- `STAGING_API_URL`
- `STAGING_BEARER_TOKEN`
- `STAGING_BRANCH_ID`

The smoke test covers health, products, secured query, sync download, and sync upload.

## Gate 3 — Turso live persistence
Workflows:
- `.github/workflows/turso-integration.yml`
- `.github/workflows/turso-deep-integration.yml`

Required secrets:
- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`

The live gates cover durable persistence, rollback, concurrency, idempotency, tenant/branch scope, isolation, and cursor behavior.

## Gate 4 — Managed Turso recovery
The repository contains a local SQLite recovery drill, but that is not proof of managed-cloud recovery.

Required operational evidence:
1. Create a disposable restore target from the production database at a known point in time.
2. Run integrity and representative read checks against the restore target.
3. Verify the expected records exist.
4. Destroy the disposable restore target.
5. Record the timestamp and result without storing credentials in Git.

Turso supports point-in-time restore by creating a new database from an existing database at a specified timestamp. urlTurso point-in-time restore documentationhttps://turso.tech/blog/turso-now-supports-database-branching-and-point-in-time-restore-eaadb8c4dce5

## Gate 5 — Client E2E
CI validates the Flutter and Python client surfaces, but release evidence must still exercise authenticated workflows against staging:
- login/authentication
- inventory
- sales
- customers
- suppliers
- installments
- maintenance
- sync/retry/conflict handling
- reports/branch/user settings where implemented

Hardware integrations remain a separate release requirement if the deployment depends on scanners/printers/cash drawers.

## Current decision
Do not label the repository production-ready until Gates 2–5 have evidence from the target staging/production environment.
