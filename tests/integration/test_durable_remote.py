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


def test_persistence_cannot_reassign_existing_record_to_another_tenant(tmp_path):
    db = tmp_path / "tenant-reassignment.db"
    a = DurableERPCommandEngine(connection=sqlite3.connect(db))
    b = DurableERPCommandEngine(connection=sqlite3.connect(db))
    try:
        a.transaction(lambda: a.create_product(
            _ctx("tenant-a-product", "tenant-a"),
            Product("p-tenant-a", "Tenant A Product", "TENANT-A-SKU", "ACCESSORY"),
        ))

        # A second tenant must not be able to see or mutate the existing record.
        from backend.functions.repositories.generic import set_tenant_scope, reset_tenant_scope
        token = set_tenant_scope("tenant-b")
        try:
            assert b.products.get("p-tenant-a") is None
            try:
                b.products.update("p-tenant-a", Product(
                    "p-tenant-a", "Tenant B Product", "TENANT-B-SKU", "ACCESSORY"
                ))
            except KeyError:
                pass
            else:
                raise AssertionError("cross-tenant update must be rejected")
        finally:
            reset_tenant_scope(token)

        # Reload from the durable boundary and prove the owner is unchanged.
        b.transaction(lambda: None)
        assert b.products.tenant_of("p-tenant-a") == "tenant-a"
        assert b.products.get("p-tenant-a").name == "Tenant A Product"
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
