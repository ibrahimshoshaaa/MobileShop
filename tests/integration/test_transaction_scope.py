from decimal import Decimal

from backend.functions.repositories.generic import current_tenant, reset_tenant_scope, set_tenant_scope
from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.commands import CommandContext
from shared.models.erp import Product


def test_transaction_restores_empty_tenant_scope_after_command():
    engine = ERPCommandEngine()
    ctx = CommandContext(
        "tx-scope",
        "user-1",
        "branch-1",
        frozenset({"products.edit"}),
        "tenant-a",
    )

    assert current_tenant() is None
    engine.transaction(lambda: engine.create_product(ctx, Product(
        "p1", "Phone", "SKU1", "PHONE_NEW", default_cost=Decimal("100")
    )))
    assert current_tenant() is None
    assert engine.products.tenant_of("p1") == "tenant-a"


def test_transaction_preserves_existing_tenant_scope():
    engine = ERPCommandEngine()
    token = set_tenant_scope("tenant-a")
    try:
        ctx = CommandContext(
            "tx-scope-2",
            "user-1",
            "branch-1",
            frozenset({"products.edit"}),
            "tenant-a",
        )
        engine.transaction(lambda: engine.create_product(ctx, Product(
            "p2", "Phone 2", "SKU2", "PHONE_NEW", default_cost=Decimal("100")
        )))
        assert current_tenant() == "tenant-a"
    finally:
        reset_tenant_scope(token)
