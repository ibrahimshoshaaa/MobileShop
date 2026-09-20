# Local/dev API server

A runnable HTTP entrypoint for the command boundary that already existed in
`backend/functions/api/http.py` and `dispatch.py`, wired to the real
production reference engine (`backend/functions/services/erp_engine.py`)
unmodified — now running through a SQLite durability layer
(`backend/functions/services/durable_engine.py`) so data survives restarts.

## Run it

```
pip install -r backend/api_server/requirements.txt
uvicorn backend.api_server.main:app --reload --port 8000
```

Then:

```
curl -X POST http://localhost:8000/command \
  -H "Authorization: Bearer dev-owner-token" \
  -H "Content-Type: application/json" \
  -d '{"commandId": "test-1", "command": "createSale", "branchId": "LOCAL_BRANCH",
       "payload": {"items": [{"product_id": "demo-product-1", "quantity": 1, "unit_price": "100"}],
                   "payments": [{"wallet_id": "demo-wallet-cash", "amount": "100"}]}}'
```

Restart the server and send the exact same request again (same
`commandId`) — you'll get the identical original result back instead of a
second sale, and every product/customer/sale from before the restart is
still there. Data lives in `backend/api_server/data/dev_erp.db`
(git-ignored).

Dev tokens (see `dev_auth.py`): `dev-owner-token` (full permissions),
`dev-cashier-token` (sales + customers + installment collection only).
Seeded data (see `dev_seed.py`, only inserted once — guarded against
re-seeding on every restart): one product (`demo-product-1`, 50 in stock),
one cash wallet (`demo-wallet-cash`), one customer (`demo-customer-1`), all
under branch `LOCAL_BRANCH`.

## What this is NOT

Still not the "deployed API" the project status doc calls for:

1. **Not Turso/libSQL.** `durable_engine.py` writes to one local SQLite
   file for this one process — not a managed remote database, and there's
   no multi-server coordination. Swapping the storage target to a real
   Turso/libSQL connection later shouldn't require touching the engine
   itself, since durability is a layer on top of it, not baked in — but
   that swap hasn't been done.
2. **No real auth.** `dev_auth.py` is a static token table. Real deployment
   needs actual Firebase ID-token verification (or another real identity
   provider) deriving `uid` / `branch_ids` / `permissions` from a trusted
   source — never from the request body itself (the engine and `http.py`
   already correctly refuse to trust anything in the payload for this; only
   the verifier itself is a stand-in here).
3. **No real hosting.** This runs on `localhost` only — no deployment,
   HTTPS, environment separation, or monitoring.

## What IS real

Command dispatch, input validation, branch scoping, permission checks,
idempotent command replay (send the same `commandId` twice — even across a
restart now — get the same result back instead of double-applying), the
full ledger/audit trail, all business rules (stock checks, payment
matching, installment math, etc.), and now durability across restarts —
that's the actual reference engine, exercised here over real HTTP.

## How the durability layer works (`durable_engine.py`)

`DurableERPCommandEngine` subclasses `ERPCommandEngine` without changing
`erp_engine.py` or `completion.py` at all. It overrides `transaction()` to:
snapshot every repository before the wrapped call runs, delegate to the
inherited `transaction()` (which still does its own in-memory
rollback-on-exception, completely unchanged), and — only once that has
already succeeded — diff the snapshots and write whatever changed to a
local SQLite `records` table via a generic dataclass (de)serializer
(`backend/functions/persistence/domain_serializer.py`). On construction, it
reloads everything back into the in-memory repositories before the engine
is used.

Two things worth knowing:
- **Only `transaction()`-wrapped mutations persist.** Calling an engine
  method directly (`engine.create_sale(...)`), the way most of the existing
  engine tests do, bypasses `transaction()` and therefore this durability
  layer entirely — that's fine for those tests (they're testing engine
  logic, not persistence), but it means seeding data for a durable engine
  must go through `engine.transaction(lambda: ...)` or `dispatch()`, not a
  bare `repo.create()` call. See `dev_seed.py` and
  `tests/integration/test_durable_engine.py` for the pattern.
- **No dedicated wallet-creation command existed** in `dispatch.py`'s
  mapping before this session — `createWallet` is now a real command
  (`create_wallet` in `completion.py`, guarded by a new `wallets.edit`
  permission), rejecting duplicate wallet names within a branch and
  rejecting any payload that tries to claim a different branch than the
  caller's own. `dev_auth.py`'s owner token includes `wallets.edit`.

## A dispatch fix made along the way (previous session)

`dispatch.py` previously had no contract-building step for `createProduct`,
`createCustomer`, or `createSupplier` (only `createSale` and
`collectInstallment` did) — so a plain JSON payload would have been passed
straight to `create_product(self, command, product)`, which expects a real
`Product` dataclass, not a dict. That's fixed, with tests in
`tests/unit/test_api_dispatch.py`.

One caveat worth knowing: a **flat** (unwrapped) payload for these three
commands can't include a `name` field, because `dispatch(engine, name,
command, **payload)` already uses `name` as its own parameter — passing
`name` again via `**payload` collides. Use the wrapped form shown above
(`payload: {"product": {...}}`) to avoid this entirely.

## Read-side query endpoints and updateProduct (this session)

The command boundary only ever handled writes — there was no way to list
anything without going straight to Python. `GET /products?branch_id=...`
is the first read endpoint, computing each product's on-hand quantity via
`engine._available_qty` (products have no quantity field of their own; it's
derived from `StockMovement` rows per branch). It requires the same
Authorization header and branch check as `/command`.

`updateProduct` was also missing from `dispatch.py` entirely (the engine
method `update_product` already existed, just never wired up) — added the
same way, with the wrapped-payload caveat applying here too: send
`{"product_id": "...", "changes": {"name": "...", ...}}`, not a flat
payload, since `changes` can include `name`.

## Desktop app connected to this server (this session)

`apps/desktop/api_client.py` (stdlib `urllib` only, no extra dependency) and
`apps/desktop/api_inventory_repo.py` let the desktop app's **Inventory tab
only** talk to this server instead of its local SQLite file. Run the
desktop app with:

```
MOBILE_SHOP_ERP_MODE=online python apps/desktop/app.py
```

This was tested for real: a live `uvicorn` subprocess, real HTTP calls (not
an in-process test client) for list/create/adjust-stock/update, all
verified end-to-end. Sales and Maintenance still use their own **offline**
product lookups even when Inventory is in online mode — wiring the rest of
the tabs (and the mobile app) the same way is further work, not done here.
This is also still just one desktop process talking to one local dev
server; it says nothing about how multiple devices would reconcile
concurrent offline changes once real sync is built.
