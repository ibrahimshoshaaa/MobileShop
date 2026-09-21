from backend.functions.api.dispatch import dispatch
from backend.functions.offline.protocol import SyncProtocol
from backend.functions.services.durable_engine import DurableERPCommandEngine
from shared.contracts.commands import CommandContext


def test_shared_connection_keeps_business_write_and_receipt_atomic(tmp_path):
    """One transaction runner covers receipt and business state; replay is single-shot."""
    engine = DurableERPCommandEngine(tmp_path / "erp.db")
    sync = SyncProtocol(connection=engine.connection, transaction=engine.transaction)
    calls = []
    envelope = {
        "command_id": "sale-atomic-1", "tenant_id": "tenant-1", "branch_id": "b1",
        "command": "createProduct",
        "payload": {"product": {"name": "شاحن", "sku": "ATOMIC-1", "product_type": "ACCESSORY"}},
    }

    def execute(item):
        calls.append(item["command_id"])
        context = CommandContext(item["command_id"], "user-1", "b1", frozenset({"products.edit"}), "tenant-1")
        return dispatch(engine, item["command"], context, **item["payload"])

    result = sync.upload([envelope], tenant_id="tenant-1", branch_id="b1", executor=execute)
    assert result["results"][0]["status"] == "APPLIED"
    assert engine.products.get("sale-atomic-1") is not None
    assert calls == ["sale-atomic-1"]

    replay = sync.upload([envelope], tenant_id="tenant-1", branch_id="b1", executor=execute)
    assert replay["results"][0]["idempotent_replay"] is True
    assert calls == ["sale-atomic-1"]
    receipt = engine.connection.execute(
        "SELECT status FROM sync_receipts WHERE tenant_id=? AND branch_id=? AND command_id=?",
        ("tenant-1", "b1", "sale-atomic-1"),
    ).fetchone()
    assert receipt[0] == "APPLIED"
    sync.close()
