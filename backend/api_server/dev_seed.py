"""Dev-only bootstrap data scoped to the development tenant."""
from __future__ import annotations

from decimal import Decimal

from backend.functions.repositories.generic import reset_tenant_scope, set_tenant_scope
from shared.models.erp import Branch, Customer, ERPUser, ERPUserRole, Product, StockMovement, Wallet


def seed_dev_data(engine) -> None:
    token = set_tenant_scope("dev-tenant")
    try:
        branch_id = "LOCAL_BRANCH"

        def _seed():
            if engine.branches.get(branch_id) is None:
                engine.branches.create("LOCAL_BRANCH", Branch("LOCAL_BRANCH", "الفرع الرئيسي", "MAIN"), tenant_id="dev-tenant")
            if engine.roles.get("dev-owner") is None:
                engine.roles.create("dev-owner", ERPUserRole(
                    "dev-owner", "مدير النظام",
                    permissions=("branches.read","branches.manage","users.read","users.manage","roles.read","roles.manage"),
                ), tenant_id="dev-tenant")
            if engine.users.get("dev-owner") is None:
                engine.users.create("dev-owner", ERPUser(
                    "dev-owner", "مدير النظام", branch_ids=(branch_id,), role_id="dev-owner",
                    permissions=("branches.read","branches.manage","users.read","users.manage","roles.read","roles.manage"),
                ), tenant_id="dev-tenant")

            if engine.products.get("demo-product-1") is None:
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
            if engine.stock.get("seed-stock-1") is None:
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
            if engine.wallets.get("demo-wallet-cash") is None:
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
            if engine.customers.get("demo-customer-1") is None:
                engine.customers.create(
                    "demo-customer-1",
                    Customer(id="demo-customer-1", name="عميل تجريبي"),
                    tenant_id="dev-tenant",
                )

        engine.transaction(_seed)
    finally:
        reset_tenant_scope(token)
