from decimal import Decimal

import pytest

from backend.functions.offline.protocol import SyncProtocol
from backend.functions.services.durable_engine import DurableERPCommandEngine
from backend.functions.repositories.generic import reset_tenant_scope, set_tenant_scope
from shared.models.erp import Product


def _envelope(command_id="cmd-crash-window"):
    return {
        "command_id": command_id,
        "tenant_id": "tenant-1",
        "branch_id": "branch-1",
        "command": "createProduct",
        "payload": {},
    }


def test_sync_business_write_and_receipt_are_atomic_across_crash(tmp_path):
    db_path = tmp_path / "erp.db"
    engine = DurableERPCommandEngine(db_path)
    sync = SyncProtocol(connection=engine._conn)

    def crashing_executor(envelope):
        token = set_tenant_scope("tenant-1")
        try:
            # This is the business write that previously could commit before
            # the separate sync receipt was marked APPLIED.
            engine.transaction(
                lambda: engine.products.create(
                    "product-1",
                    Product(
                        id="product-1",
                        name="Test Phone",
                        sku="TEST-1",
                        product_type="PHONE",
                        selling_price=Decimal("100"),
                        tenant_id="tenant-1",
                    ),
                    tenant_id="tenant-1",
                )
            )
        finally:
            reset_tenant_scope(token)
        # Simulate the process dying immediately before the receipt update.
        raise KeyboardInterrupt("simulated process crash")

    with pytest.raises(KeyboardInterrupt):
        sync.upload([_envelope()], tenant_id="tenant-1", branch_id="branch-1", executor=crashing_executor)

    # A real process crash closes the connection and rolls back the open
    # transaction. Re-open from disk to model the next server process.
    engine.close()

    restarted = DurableERPCommandEngine(db_path)
    restarted_sync = SyncProtocol(connection=restarted._conn)
    assert restarted.products.get("product-1") is None
    assert restarted_sync._read_receipt("tenant-1", "branch-1", "cmd-crash-window") is None

    executions = {"count": 0}

    def successful_executor(envelope):
        executions["count"] += 1
        token = set_tenant_scope("tenant-1")
        try:
            return restarted.transaction(
                lambda: restarted.products.create(
                    "product-1",
                    Product(
                        id="product-1",
                        name="Test Phone",
                        sku="TEST-1",
                        product_type="PHONE",
                        selling_price=Decimal("100"),
                        tenant_id="tenant-1",
                    ),
                    tenant_id="tenant-1",
                )
            ).__dict__
        finally:
            reset_tenant_scope(token)

    result = restarted_sync.upload(
        [_envelope()],
        tenant_id="tenant-1",
        branch_id="branch-1",
        executor=successful_executor,
    )
    assert result["results"][0]["status"] == "APPLIED"
    assert executions["count"] == 1
    assert restarted.products.get("product-1") is not None

    receipt = restarted_sync._read_receipt("tenant-1", "branch-1", "cmd-crash-window")
    assert receipt[0] == "APPLIED"
