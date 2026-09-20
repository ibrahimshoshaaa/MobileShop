# Mobile Shop ERP

Production-oriented implementation of the Mobile Shop ERP Master Specification.

## Current status
- Phase 0 foundation: implemented and tested.
- Phase 1 domain foundation: users/roles/branch authorization/branches/settings implemented and tested.
- Firebase persistence is the next integration boundary; the current repository adapter is intentionally in-memory for deterministic tests.

## Architecture
`UI -> Command -> AuthZ/Validation -> Transaction -> Events/Ledger/Stock/Wallet/Audit -> Derived balances/reports`

Clients: Python/Flet POS and Flutter/Dart/Riverpod mobile/admin.
Backend: Firebase Auth + Firestore + Cloud Functions/server-side logic.

## Run tests
```bash
pytest -q
```

The Master Specification remains authoritative. No business rule is invented where the specification is silent.

## Release note — SQL durability hardening
- Local SQLite store now uses explicit `BEGIN IMMEDIATE` transactions with rollback on exceptions.
- Command idempotency is tenant/branch-bound; cross-tenant reuse is rejected.
- Pending outbox reads can be scoped by tenant and branch.
- SQLite durability settings include WAL and `synchronous=FULL`.
- This remains a development/reference release until the complete UI, server API, Turso deployment, authentication adapter, and end-to-end multi-branch sync are deployed and tested in a staging environment.
