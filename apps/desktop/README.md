# Desktop UI

Tkinter POS shell with Arabic labels, ported from the mobile app's working
modules — same validation rules on both platforms:

- `inventory_repo.py` / `inventory_tab.py` — product catalog, stock, low-stock badge.
- `sales_repo.py` / `sales_tab.py` — cart, discount, split payments, void.
- `customers_repo.py` / `customers_tab.py` — customer list + picker (shared with Sales/Installments/Maintenance).
- `suppliers_repo.py` / `suppliers_tab.py` — supplier directory.
- `installments_repo.py` / `installments_tab.py` — plan calculation + payment collection.
- `maintenance_repo.py` / `maintenance_tab.py` — ticket status state machine, parts usage, delivery.
- `expenses_repo.py` / `expenses_tab.py` — categorized expenses, today's total.

## Offline mode (default)

`local_store.py` reuses the production
`backend/functions/persistence/sqlite_repository.SQLiteRepository` as-is, so
this app dogfoods the same durable local store the backend already ships,
instead of a second bespoke one. Each desktop install gets its own SQLite
file under `apps/desktop/data/` (git-ignored) — there is no sync between
devices in this mode; every mutation is queued in the local command outbox
for a future sync protocol to replay.

Run with:

```
python apps/desktop/app.py
```

## Online mode (Inventory tab only, new)

Set `MOBILE_SHOP_ERP_MODE=online` to make the **Inventory tab** talk to a
real `backend/api_server` instance over HTTP instead of local SQLite:

```
MOBILE_SHOP_ERP_MODE=online python apps/desktop/app.py
```

Optional env vars: `MOBILE_SHOP_ERP_API_URL` (default
`http://localhost:8000`), `MOBILE_SHOP_ERP_API_TOKEN` (default
`dev-owner-token` — see `backend/api_server/dev_auth.py`). The server needs
to already be running (`uvicorn backend.api_server.main:app`) — see
`backend/api_server/README.md`.

This was verified against a real running server (not a mocked client):
listing, creating, adjusting stock, and updating a product all worked over
an actual HTTP connection. Scope of this step: **Inventory only** — Sales
and Maintenance still look up products through the offline `inventory_repo`
even when Inventory itself is online, since `ProductPickerWindow` defaults
to it. Every other tab (Sales, Customers, Suppliers, Installments,
Maintenance, Expenses) is offline-only for now; wiring them the same way is
further work, and would need matching read/write endpoints added to the API
server first (only products have a `GET` endpoint so far).

## Known deviations from the backend's exact domain model

(documented in code comments too, and identical to the mobile app's)
quantity lives directly on the product record instead of being derived from
`StockMovement` rows in offline mode, and money is plain `float` rounded to
2 decimals instead of `Decimal` — simplifications carried over from the
mobile port. In online mode, quantity IS the server's real
`StockMovement`-derived figure (see `backend/api_server`'s `GET /products`),
so that particular gap closes for whichever tab is online.

Never mutate financial state directly in UI beyond what's here — for
anything still in offline mode, these repo modules are what should start
submitting through the real API instead of writing straight to local SQLite
once the rest of the tabs get the same online-mode treatment Inventory just did.
