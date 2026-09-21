import threading
from concurrent.futures import ThreadPoolExecutor

from backend.functions.offline.protocol import SyncProtocol
from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.commands import CommandContext
from shared.models.erp import Customer, Product, Supplier


def test_cross_tenant_customer_and_supplier_are_invisible():
    engine = ERPCommandEngine()
    ctx_a = CommandContext("ca", "ua", "b1", frozenset({"customers.edit", "suppliers.edit"}), "tenant-a")
    ctx_b = CommandContext("cb", "ub", "b1", frozenset({"customers.edit", "suppliers.edit"}), "tenant-b")
    customer = Customer("c1", "Tenant A customer")
    supplier = Supplier("s1", "Tenant A supplier", branch_ids=("b1",))
    engine.create_customer(ctx_a, customer)
    engine.create_supplier(CommandContext("cs", "ua", "b1", frozenset({"suppliers.edit"}), "tenant-a"), supplier)
    assert engine.customers.get("c1") is customer
    assert engine.suppliers.get("s1") is supplier
    engine.create_customer(ctx_b, Customer("c2", "Tenant B customer"))
    assert engine.customers.get("c1") is None
    assert engine.suppliers.get("s1") is None


def test_concurrent_sync_upload_is_idempotent(tmp_path):
    sync = SyncProtocol(tmp_path / "sync.db")
    calls = []
    lock = threading.Lock()

    def execute(envelope):
        with lock:
            calls.append(envelope["command_id"])
        return {"ok": True}

    envelope = {"command_id": "same", "tenant_id": "t1", "branch_id": "b1", "payload": {}}
    def run():
        return sync.upload([envelope], tenant_id="t1", branch_id="b1", executor=execute)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: run(), range(8)))

    assert calls == ["same"]
    assert all(r["results"][0]["status"] in {"APPLIED"} for r in results)
    sync.close()


def test_concurrent_uploads_across_two_sync_workers_execute_once(tmp_path):
    db = tmp_path / "shared-sync.db"
    left = SyncProtocol(db)
    right = SyncProtocol(db)
    calls = []
    lock = threading.Lock()
    started = threading.Barrier(2)

    def execute(envelope):
        with lock:
            calls.append(envelope["command_id"])
        started.wait(timeout=5)
        return {"ok": True}

    envelope = {"command_id": "cross-worker", "tenant_id": "t1", "branch_id": "b1", "payload": {"x": 1}}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda sync: sync.upload([envelope], tenant_id="t1", branch_id="b1", executor=execute),
            [left, right],
        ))

    assert calls == ["cross-worker"]
    statuses = {r["results"][0]["status"] for r in results}
    assert statuses == {"APPLIED", "PROCESSING"}
    left.close()
    right.close()
