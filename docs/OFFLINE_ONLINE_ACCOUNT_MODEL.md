# Offline-first + Cloud Account Model

## Product behavior

1. The first launch works in **Offline mode** without requiring registration.
2. The owner can open **Settings → Cloud account** and enable Online mode.
3. The owner enters email and password only for authentication. The password is
   transmitted over TLS to the API and is never stored as plaintext in the app
   database, tenant records, or branch records.
4. The server returns a linked account/tenant identity and the branches the
   authenticated user is authorized to access.
5. Installing the app on another branch/device uses **Sign in / Link existing
   account**, not **Create new account**. It joins the same tenant and receives
   only authorized branch data.
6. Local offline data is scoped to a device profile until the owner explicitly
   links it. The sync engine must reconcile records using immutable IDs and
   idempotent command IDs.

## Required server entities

- `accounts`: identity metadata, email index, status, createdAt.
- `tenants`: the business/company boundary.
- `branches`: tenant-owned branches.
- `account_memberships`: account → tenant/branch + role/permissions.
- `device_links`: device key, account/tenant, lastSyncCursor, revokedAt.
- `sync_operations`: commandId, deviceId, state, conflict/error metadata.

## Security rules

- Store password hashes only in a dedicated identity provider/auth service;
  never in ERP tables or local SQLite.
- Do not trust branch IDs or permissions supplied by the client.
- Every cloud command is authorized against the server-side membership.
- A device can be revoked without deleting accounting history.
- Sensitive conflicts (stock, IMEI, payments, returns, installments) require
  server validation; they must not silently overwrite another branch's data.
