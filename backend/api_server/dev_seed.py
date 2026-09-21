"""Dev-only bootstrap data scoped to the development tenant."""
from __future__ import annotations

from decimal import Decimal

from backend.functions.repositories.generic import reset_tenant_scope, set_tenant_scope
from shared.models.erp import Customer, Product, StockMovement, Wallet


def seed_dev_data(engine) -> None:
    token = set_tenant_scope("dev-tenant")
    try:
        if engine.products.get("demo-product-1") is not None:
            return
        branch_id = "LOCAL_BRANCH"

        def _seed():
            engine.products.create(
                "demo-product-1",
                Product(
                    id="demo-product-1",
                    name="منتج تجريبي",
                    sku="DEMO-1",
                    product_type="ACCESSORY",
                    selling_price=Decimal("100"),
                    default_cost=Decimal("60"),
                ),
                tenant_id="dev-tenant",
            )
            engine.stock.create(
                "seed-stock-1",
                StockMovement(
                    id="seed-stock-1",
                    branch_id=branch_id,
                    product_id="demo-product-1",
                    quantity=Decimal("50"),
                    movement_type="OPENING_BALANCE",
                    reference_id="dev-seed",
                ),
                tenant_id="dev-tenant",
            )
            engine.wallets.create(
                "demo-wallet-cash",
                Wallet(
                    id="demo-wallet-cash",
                    branch_id=branch_id,
                    name="الخزينة النقدية",
                    wallet_type="CASH",
                ),
                tenant_id="dev-tenant",
            )
            engine.customers.create(
                "demo-customer-1",
                Customer(id="demo-customer-1", name="عميل تجريبي"),
                tenant_id="dev-tenant",
            )

        engine.transaction(_seed)
    finally:
        reset_tenant_scope(token)
