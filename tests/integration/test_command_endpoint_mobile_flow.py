"""Exercises the *actual* HTTP boundary (`POST /command`) with the exact
payload shapes apps/admin_mobile queues, end to end.

Every other contract test (test_mobile_client_contract.py) calls
`dispatch()` directly in-process. Per the report, the real path
(/command, /sync/upload) through FastAPI + auth + DurableERPCommandEngine
had never actually been exercised — this fills that gap for the flows the
report flags as newly working (maintenance transitions) and previously
fixed (product+opening-stock, sale, wallet aliasing).

Uses a fresh temp sqlite file per test run (not the shared dev_erp.db) so
this suite never depends on, or pollutes, dev-server state.
"""
import os
import tempfile
import uuid
from pathlib import Path

import pytest


@pytest.fixture()
def client():
    """Swaps main.py's shared engine for a fresh, temp-file-backed one so
    this suite never depends on, or pollutes, the real dev_erp.db (the
    module itself is only imported once per test session either way)."""
    from fastapi.testclient import TestClient
    import backend.api_server.main as main_module
    from backend.api_server.dev_seed import seed_dev_data
    from backend.functions.services.durable_engine import DurableERPCommandEngine

    tmp_db = Path(tempfile.gettempdir()) / f"mobile-shop-test-{uuid.uuid4().hex}.db"
    original_engine = main_module.engine
    main_module.engine = DurableERPCommandEngine(tmp_db)
    seed_dev_data(main_module.engine)
    try:
        yield TestClient(main_module.app)
    finally:
        main_module.engine = original_engine
        tmp_db.unlink(missing_ok=True)


HEADERS = {"Authorization": "Bearer dev-owner-token", "Content-Type": "application/json"}
BRANCH = "LOCAL_BRANCH"


def _command(client, command_id, command, payload):
    return client.post(
        "/command",
        headers=HEADERS,
        json={"commandId": command_id, "command": command, "branchId": BRANCH, "payload": payload},
    )


def test_unauthorized_request_is_rejected(client):
    resp = client.post(
        "/command",
        json={"commandId": "x", "command": "createSale", "branchId": BRANCH, "payload": {}},
    )
    assert resp.status_code == 401


def test_product_with_opening_stock_then_sale_over_http(client):
    uid = uuid.uuid4().hex[:8]
    product_id = f"p-{uid}"

    resp = _command(client, f"cmd-create-{uid}", "createProduct", {
        "id": product_id, "name": "Cable", "sku": f"SKU-{uid}",
        "product_type": "ACCESSORY", "selling_price": 50, "default_cost": 20,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    resp = _command(client, f"cmd-stock-{uid}", "adjustStock", {
        "product_id": product_id, "delta": 10, "reason": "opening",
    })
    assert resp.status_code == 200, resp.text

    resp = _command(client, f"cmd-cust-{uid}", "createCustomer", {"id": f"cust-{uid}", "name": "Ali"})
    assert resp.status_code == 200, resp.text

    resp = _command(client, f"sale-{uid}", "createSale", {
        "customer_id": f"cust-{uid}",
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 50}],
        "payments": [{"wallet_id": "wallet-cash", "amount": 100}],
        "discount": 0,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    # Idempotency over the real HTTP boundary: replaying the same commandId
    # must return the original result, not double-apply the sale.
    replay = _command(client, f"sale-{uid}", "createSale", {
        "customer_id": f"cust-{uid}",
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 50}],
        "payments": [{"wallet_id": "wallet-cash", "amount": 100}],
        "discount": 0,
    })
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == resp.json()["data"]["id"]


def test_maintenance_ticket_transitions_to_ready_over_http(client):
    """The exact fix from this session, replayed through the real endpoint
    (not dispatch() directly): transitionMaintenance must actually route."""
    uid = uuid.uuid4().hex[:8]
    _command(client, f"cust-{uid}", "createCustomer", {"id": f"cust-{uid}", "name": "Sara"})
    resp = _command(client, f"mnt-{uid}", "createMaintenanceTicket", {
        "customer_id": f"cust-{uid}", "device": "Phone", "problem": "screen", "imei": None,
    })
    assert resp.status_code == 200, resp.text

    for i, status in enumerate(("DIAGNOSING", "WAITING_CUSTOMER", "IN_PROGRESS", "READY")):
        resp = _command(client, f"mnt-{uid}-t{i}", "transitionMaintenance", {
            "ticket_id": f"mnt-{uid}", "new_status": status,
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == status


def test_command_endpoint_writes_are_visible_to_sync_changes(client):
    """Report item 8 ('the Download Queue hasn't been reviewed since the id
    changes') undersells what was actually going on: /command never wrote a
    sync_events row at all — only /sync/upload's executor path
    (SyncProtocol.upload -> record COMMAND_APPLIED) did that (see
    backend/functions/offline/protocol.py). Since pushCommandOnline (the
    app's primary online-write path, called by nearly every
    sqlite_*_repository.dart write) always hits /command directly, a write
    made this way was durable and idempotent on the server, but invisible
    to a *second device* draining /sync/changes (DownloadQueue.drain()) —
    nothing in the mobile app calls /sync/upload today (5.1's Upload Queue
    doesn't exist yet per the report), so in practice no online write was
    visible to a second device's download queue at all.

    Fixed by SyncProtocol.record_applied_event(), called from the /command
    handler on every successful command. This test confirms a product
    created via /command now actually appears in /sync/changes.
    """
    uid = uuid.uuid4().hex[:8]
    product_id = f"p-sync-{uid}"
    resp = _command(client, f"cmd-sync-{uid}", "createProduct", {
        "id": product_id, "name": "Cable", "sku": f"SKU-SYNC-{uid}",
        "product_type": "ACCESSORY", "selling_price": 50, "default_cost": 20,
    })
    assert resp.status_code == 200, resp.text

    # The product exists on the server...
    products = client.get(f"/products?branch_id={BRANCH}", headers=HEADERS).json()
    assert any(p.get("id") == product_id for p in products["data"])

    # ...and a second device's download queue, starting from cursor 0,
    # now sees the change for it too.
    changes = client.get(f"/sync/changes?branch_id={BRANCH}&cursor=0&limit=1000", headers=HEADERS).json()
    matching = [c for c in changes["data"]["changes"] if c.get("payload", {}).get("id") == product_id]
    assert len(matching) == 1
    assert matching[0]["command_id"] == f"cmd-sync-{uid}"

    # Replaying the same commandId (idempotent retry) must not duplicate
    # the sync_events row.
    replay = _command(client, f"cmd-sync-{uid}", "createProduct", {
        "id": product_id, "name": "Cable", "sku": f"SKU-SYNC-{uid}",
        "product_type": "ACCESSORY", "selling_price": 50, "default_cost": 20,
    })
    assert replay.status_code == 200
    changes_after_replay = client.get(f"/sync/changes?branch_id={BRANCH}&cursor=0&limit=1000", headers=HEADERS).json()
    matching_after_replay = [
        c for c in changes_after_replay["data"]["changes"] if c.get("payload", {}).get("id") == product_id
    ]
    assert len(matching_after_replay) == 1


def test_unsupported_command_returns_domain_error_not_500(client):
    resp = _command(client, "cmd-bad", "notARealCommand", {})
    assert resp.status_code in (400, 422)
    assert resp.json()["ok"] is False
    assert resp.json()["error"]["code"] == "INVALID_INPUT"
