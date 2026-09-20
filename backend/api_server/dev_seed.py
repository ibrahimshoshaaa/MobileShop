"""Dev-only bootstrap data for the local API server.

Inserts records directly into the engine's repositories, bypassing the
command boundary entirely — that's fine for a one-time local dev bootstrap,
but is exactly the kind of direct-mutation the rest of this codebase
(correctly) refuses to allow anywhere else. Never do this against a real
deployment.

Wrapped in engine.transaction() (rather than calling repo.create()
directly) so that, when the engine is a DurableERPCommandEngine, this seed
data is also written through to SQLite — otherwise it would vanish on the
very next restart while everything else the durability layer covers
persists, which would be a confusing inconsistency. Guarded by an
existence check so restarting the server doesn't try to recreate (and
ValueError on) records that already persisted from a previous run.
"""
from __future__ import annotations

from decimal import Decimal

from backend.functions.repositories.generic import set_tenant_scope, reset_tenant_scope
from shared.models.erp import Customer, Product, StockMovement, Wallet


def seed_dev_data(engine) -> None:
    if engine.products.get("demo-product-1") is not None:
        return  # already seeded (durable engine reloaded it from a previous run)

    branch_id = "LOCAL_BRANCH"

    def _seed():
        engine.products.create("demo-product-1", Product(
            id="demo-product-1", name="منتج تجريبي", sku="DEMO-1", product_type="ACCESSORY",
            selling_price=Decimal("100"), default_cost=Decimal("60"),
        ))
        engine.stock.create("seed-stock-1", StockMovement(
            id="seed-stock-1", branch_id=branch_id, product_id="demo-product-1",
            quantity=Decimal("50"), movement_type="OPENING_BALANCE", reference_id="dev-seed",
        ))
        engine.wallets.create("demo-wallet-cash", Wallet(
            id="demo-wallet-cash", branch_id=branch_id, name="الخزينة النقدية", wallet_type="CASH",
        ))
        engine.customers.create("demo-customer-1", Customer(id="demo-customer-1", name="عميل تجريبي"))

    engine.transaction(_seed)
