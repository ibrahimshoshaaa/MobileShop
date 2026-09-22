# Security Review — Final Pass

## Fixed in this pass
- HTTP command handler no longer trusts client-supplied permissions.
- Branch access is checked from trusted server claims.
- Customer transfer direction now follows cash/digital wallet types.
- Manual transfer commission override requires a dedicated permission.
- Firestore rules default-deny and block direct client writes to financial source-of-truth collections.
- Security deployment contract documents token verification and environment separation.

## Required production controls
- Firebase Admin token verification in the deployed HTTP/callable adapter.
- Firestore rules/indexes tested in the emulator before production.
- Secrets only in server environment/secret manager; never in client code.
- Separate dev/staging/prod Firebase projects.
- Automated backups/exports and recovery drills.
- Monitoring for failed commands, transaction conflicts, sync failures, auth failures,
  printer failures, and unusual wallet adjustments.

## Integrity model
Financial changes must pass through server commands, authorization, validation,
transaction handling, event/ledger/stock updates, and audit logging. Completed
financial history is not hard-deleted.
