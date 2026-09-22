# Mobile Shop ERP

Production-oriented implementation of the Mobile Shop ERP Master Specification.

## Current release-gate status
- Backend security, tenant isolation, durable transactions, idempotency, ERP regression coverage, and Turso integration paths are implemented.
- GitHub CI now validates the backend plus the client surfaces on every release branch/main push and pull request.
- Authenticated staging smoke automation is present and runs on the release branch/main when the staging secrets are configured.
- Turso live integration and deep-integration workflows now run on the release branch/main when Turso secrets are configured.
- Local SQLite backup/restore integrity drill is implemented.
- **Production release is not declared complete until a real staging smoke run, a real managed-Turso point-in-time backup/restore verification, and end-to-end client workflows have been exercised.**

## Architecture
`UI -> Command -> AuthZ/Validation -> Transaction -> Events/Ledger/Stock/Wallet/Audit -> Derived balances/reports`

Clients: Python/Flet POS and Flutter/Dart/Riverpod mobile/admin.
Backend: Firebase Auth + Firestore/Cloud Functions boundaries plus Turso/libSQL durable production path.

## CI / release validation
```bash
pytest -q
python -m compileall -q backend shared tests apps/desktop apps/pos
```

The GitHub Actions pipeline also runs Bandit, pip-audit, Flutter analysis for `apps/admin_mobile`, and the live Turso/staging gates when their deployment secrets are available.

## Persistence and recovery
- Local SQLite uses explicit durable transactions with rollback on exceptions.
- Command idempotency is tenant/branch-bound.
- Tenant and branch scope are enforced across the secured API/sync path.
- Turso/libSQL is required for production startup.
- `scripts/backup_restore_check.py` verifies a portable SQLite backup/restore drill.
- The managed Turso recovery gate is intentionally separate: it must verify a real point-in-time restore against a disposable database in the Turso account.

## Client release scope
The repository contains:
- Flutter admin/mobile surface under `apps/admin_mobile`.
- Python desktop POS under `apps/desktop`.
- POS runtime boundary under `apps/pos`.

The release CI validates that these surfaces compile/analyze, but this is not equivalent to a full production E2E run. The remaining E2E work includes authenticated API workflows across the actual clients, full online coverage for desktop modules, offline-sync UI behavior, reporting/users/branch settings, and hardware integrations.

The Master Specification remains authoritative. No business rule is invented where the specification is silent.
