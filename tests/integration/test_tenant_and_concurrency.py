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


def test_stale_processing_claim_is_reclaimed(tmp_path):
    sync = SyncProtocol(tmp_path / "stuck.db")
    envelope = {"command_id": "stuck", "tenant_id": "t1", "branch_id": "b1", "payload": {"x": 1}}
    request_hash = __import__("hashlib").sha256(
        __import__("json").dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    sync.db.execute(
        "INSERT INTO sync_receipts(tenant_id,branch_id,command_id,status,request_hash,claimed_at) VALUES(?,?,?,?,?,?)",
        ("t1", "b1", "stuck", "PROCESSING", request_hash, 1.0),
    )
    sync.db.commit()
    calls = []

    result = sync.upload(
        [envelope],
        tenant_id="t1",
        branch_id="b1",
        executor=lambda _: calls.append("executed"),
    )

    assert result["results"][0]["status"] == "APPLIED"
    assert calls == ["executed"]
    row = sync.db.execute(
        "SELECT status FROM sync_receipts WHERE tenant_id=? AND branch_id=? AND command_id=?",
        ("t1", "b1", "stuck"),
    ).fetchone()
    assert row == ("APPLIED",)
    sync.close()


def test_concurrent_uploads_across_two_sync_workers_execute_once(tmp_path):
    db = tmp_path / "shared-sync.db"
    left = SyncProtocol(db)
    right = SyncProtocol(db)
    calls = []
    lock = threading.Lock()
    started = threading.Event()
    release = threading.Event()

    def execute(envelope):
        with lock:
            calls.append(envelope["command_id"])
        started.set()
        assert release.wait(timeout=5)
        return {"ok": True}

    envelope = {"command_id": "cross-worker", "tenant_id": "t1", "branch_id": "b1", "payload": {"x": 1}}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(sync.upload, [envelope], tenant_id="t1", branch_id="b1", executor=execute)
            for sync in (left, right)
        ]
        assert started.wait(timeout=5)
        release.set()
        results = [future.result() for future in futures]

    assert calls == ["cross-worker"]
    statuses = {r["results"][0]["status"] for r in results}
    assert statuses <= {"APPLIED", "PROCESSING", "RETRYABLE"}
    assert "APPLIED" in statuses
    left.close()
    right.close()
