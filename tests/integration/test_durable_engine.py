"""End-to-end tests for DurableERPCommandEngine.

Important: transaction() (and therefore this durability layer) is only
invoked via dispatch() — the same boundary the real API server uses (see
backend/functions/api/dispatch.py / backend/api_server/main.py). Calling
engine methods directly (as most of the existing engine tests do, e.g.
tests/integration/test_full_matrix.py) bypasses transaction() entirely, so
these tests go through dispatch() throughout, exactly like a real request
would. Wallet creation has no dispatch command yet, so it's seeded via
engine.transaction() directly, which is the same routing dispatch() itself
uses under the hood.
"""
from decimal import Decimal

from shared.contracts.commands import CommandContext
from shared.contracts.errors import DomainError
from shared.models.erp import Wallet
from backend.functions.api.dispatch import dispatch
from backend.functions.services.durable_engine import DurableERPCommandEngine


def ctx(cid, perms=None, branch="b1"):
    perms = perms or {"sales.create", "products.edit", "stock.adjust"}
    return CommandContext(cid, "u1", branch, frozenset(perms))


def seed_wallet(engine, wallet_id="w1"):
    engine.transaction(lambda: engine.wallets.create(wallet_id, Wallet(id=wallet_id, branch_id="b1", name="نقدي", wallet_type="CASH")))


def test_data_survives_engine_restart(tmp_path):
    db_path = tmp_path / "erp.db"

    e1 = DurableERPCommandEngine(db_path)
    dispatch(e1, "createProduct", ctx("p1"), product={
        "name": "شاحن", "sku": "SKU-1", "product_type": "ACCESSORY",
        "selling_price": "100", "default_cost": "50",
    })
    seed_wallet(e1)
    dispatch(e1, "adjustStock", ctx("seed"), product_id="p1", quantity=10, cost=50)
    sale = dispatch(e1, "createSale", ctx("sale-1"), items=[{"product_id": "p1", "quantity": 2, "unit_price": "100"}],
                     payments=[{"wallet_id": "w1", "amount": "200"}])
    assert sale.total == 200
    e1.close()

    # Fresh engine instance, same db file — simulates a process restart.
    e2 = DurableERPCommandEngine(db_path)
    assert e2.products.get("p1").sku == "SKU-1"
    assert e2.sales.get("sale-1").total == Decimal("200")
    assert e2._available_qty("b1", "p1") == Decimal("8")  # 10 seeded - 2 sold
    e2.close()


def test_idempotency_survives_restart(tmp_path):
    db_path = tmp_path / "erp.db"

    e1 = DurableERPCommandEngine(db_path)
    dispatch(e1, "createProduct", ctx("p1"), product={"name": "شاحن", "sku": "SKU-1", "product_type": "ACCESSORY"})
    seed_wallet(e1)
    dispatch(e1, "adjustStock", ctx("seed"), product_id="p1", quantity=5, cost=0)
    first = dispatch(e1, "createSale", ctx("sale-1"), items=[{"product_id": "p1", "quantity": 1, "unit_price": "10"}],
                      payments=[{"wallet_id": "w1", "amount": "10"}])
    e1.close()

    e2 = DurableERPCommandEngine(db_path)
    # Replaying the same commandId after a restart must return the original
    # result, not re-execute (which would double-decrement stock).
    replayed = dispatch(e2, "createSale", ctx("sale-1"), items=[{"product_id": "p1", "quantity": 1, "unit_price": "10"}],
                         payments=[{"wallet_id": "w1", "amount": "10"}])
    assert replayed == first
    assert e2._available_qty("b1", "p1") == Decimal("4")  # only decremented once, ever
    e2.close()


def test_failed_transaction_does_not_persist(tmp_path):
    db_path = tmp_path / "erp.db"

    e1 = DurableERPCommandEngine(db_path)
    dispatch(e1, "createProduct", ctx("p1"), product={"name": "شاحن", "sku": "SKU-1", "product_type": "ACCESSORY"})
    seed_wallet(e1)
    # No stock adjusted — this sale must fail with INSUFFICIENT_STOCK and
    # roll back cleanly, both in memory and on disk.
    try:
        dispatch(e1, "createSale", ctx("sale-1"), items=[{"product_id": "p1", "quantity": 1, "unit_price": "10"}],
                 payments=[{"wallet_id": "w1", "amount": "10"}])
        assert False, "expected DomainError"
    except DomainError as exc:
        assert exc.code == "INSUFFICIENT_STOCK"
    e1.close()

    e2 = DurableERPCommandEngine(db_path)
    assert e2.sales.get("sale-1") is None
    # The product WAS created via its own successful dispatch()/transaction()
    # call above (that one succeeded on its own), so it correctly persisted
    # and reloads here — only the failed sale is absent.
    assert e2.products.get("p1").sku == "SKU-1"
    e2.close()


def test_tenant_scope_survives_durable_restart(tmp_path):
    from backend.functions.services.durable_engine import DurableERPCommandEngine
    from shared.contracts.commands import CommandContext
    from shared.models.erp import Product

    db = tmp_path / "tenant.db"
    ctx_a = CommandContext("c-a", "u-a", "b1", frozenset({"products.edit"}), "tenant-a")
    ctx_b = CommandContext("c-b", "u-b", "b1", frozenset({"products.edit"}), "tenant-b")

    engine = DurableERPCommandEngine(db)
    engine.create_product(ctx_a, Product("p-a", "A", "SKU-A", "ACCESSORY"))
    engine.close()

    reopened = DurableERPCommandEngine(db)
    reopened.create_product(ctx_b, Product("p-b", "B", "SKU-B", "ACCESSORY"))
    assert reopened.products.get("p-a") is None
    assert reopened.products.get("p-b") is not None
    reopened.close()
