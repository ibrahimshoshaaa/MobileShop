# Mobile Shop ERP — P0 Atomic Sync Branch Notes

> This file is maintained with the implementation PR. Scope changes must update it in the same PR.

## P0 status

- ✅ `DurableERPCommandEngine` exposes its connection and supports nested transaction participation.
- ✅ `SyncProtocol` accepts a shared connection and transaction runner.
- ✅ Sync receipt claim, business execution, receipt update, and sync event append can share one transaction boundary.
- ✅ Added `tests/integration/test_sync_atomicity.py` to verify idempotent replay and receipt state.

## Verification

- Pending: run the full pytest suite, lint/type checks, and the targeted integration tests on GitHub Actions.
- The branch must not be described as production-ready until those checks pass.
