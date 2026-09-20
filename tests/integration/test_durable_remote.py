import sqlite3
from decimal import Decimal

from backend.functions.services.durable_engine import DurableERPCommandEngine
from shared.contracts.commands import CommandContext
from shared.models.erp import Product


def _ctx(command_id, tenant="tenant-a"):
    return CommandContext(
        command_id,
        "user-1",
        "branch-1",
        frozenset({"products.edit"}),
        tenant,
    )


def test_remote_mode_refreshes_shared_sql_state_before_transaction(tmp_path):
    db = tmp_path / "shared.db"
    a = DurableERPCommandEngine(connection=sqlite3.connect(db))
    b = DurableERPCommandEngine(connection=sqlite3.connect(db))
    try:
        a.transaction(lambda: a.create_product(
            _ctx("create"),
            Product("p1", "Phone", "SKU1", "PHONE_NEW", default_cost=Decimal("100")),
        ))

        # Worker B started with the old in-memory snapshot. Remote mode must
        # refresh from SQL before taking its transaction snapshot.
        a.transaction(lambda: a.update_product(_ctx("update-a"), "p1", name="Phone A"))
        assert b.products.get("p1") is None

        def fail_after_local_mutation():
            assert b.products.get("p1").name == "Phone A"
            b.products.update("p1", Product(
                "p1", "Broken", "SKU1", "PHONE_NEW", default_cost=Decimal("100")
            ))
            raise RuntimeError("forced failure")

        try:
            b.transaction(fail_after_local_mutation)
        except RuntimeError:
            pass
        else:
            raise AssertionError("transaction should fail")

        assert b.products.get("p1").name == "Phone A"
    finally:
        a.close()
        b.close()


def test_remote_persistence_keeps_tenant_metadata(tmp_path):
    db = tmp_path / "tenant.db"
    a = DurableERPCommandEngine(connection=sqlite3.connect(db))
    b = DurableERPCommandEngine(connection=sqlite3.connect(db))
    try:
        a.transaction(lambda: a.create_product(
            _ctx("tenant-record"),
            Product("p-tenant", "Tenant Product", "TENANT-SKU", "ACCESSORY"),
        ))
        assert a.products.tenant_of("p-tenant") == "tenant-a"

        b.transaction(lambda: None)
        assert b.products.tenant_of("p-tenant") == "tenant-a"
    finally:
        a.close()
        b.close()
