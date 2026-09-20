# Phase 0 — Foundation

## Source-of-truth constraints
The Master Specification requires server-authoritative validation for sales, returns, wallet changes, transfers, purchases, maintenance parts, installment collections, permissions and financial adjustments. It also requires multi-branch support, auditability, historical cost snapshots, transactional updates and no destructive financial deletion.

## Implemented now
- Repository/module boundaries.
- Shared roles, product/event enums.
- Command context and initial command contracts.
- Domain error model.
- Permission guard.
- Money validation/rounding.
- Transfer commission calculation with default 1% and explicit manual override.
- Phase-0 unit tests.

## Intentionally not faked
Firestore persistence, Auth integration, ledger posting, stock mutation and wallet balances are not mocked as completed business logic. They are Phase-1 implementation work and must be transactional/server-authoritative.
