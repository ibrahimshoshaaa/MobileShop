from decimal import Decimal

from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.commands import CommandContext, CreateSaleCommand
from shared.models.erp import Customer, Product, Wallet


def ctx(cid, perms):
    return CommandContext(cid, "u1", "b1", frozenset(perms), "tenant-a")


def seed():
    e = ERPCommandEngine()
    e.products.create("p1", Product("p1", "Phone", "SKU1", "PHONE_NEW", default_cost=Decimal("100")))
    e.wallets.create("cash", Wallet("cash", "b1", "Cash", "CASH"))
    e.ledger.create("opening", {
        "id": "opening", "branch_id": "b1", "account_id": "wallet:cash",
        "debit": Decimal("2000"), "credit": Decimal("0")
    })
    e.adjust_stock(ctx("stock", {"stock.adjust"}), "p1", Decimal("5"), Decimal("100"))
    e.customers.create("c1", Customer("c1", "Customer"))
    return e


def test_installment_collection_balances_principal_and_interest():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("sale-credit", {"sales.create"}), "c1",
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("100")},), (),
    ))
    plan = e.create_installment_plan(
        ctx("plan", {"installments.create"}), sale.id, "c1",
        Decimal("0"), Decimal("10"), 2,
    )
    payment = e.collect_installment(
        ctx("installment-pay", {"installments.collect"}), plan.id,
        Decimal("105"), "cash",
    )
    entries = [x for x in e.ledger.all() if getattr(x, "reference_id", None) == plan.id]
    assert sum((x.debit for x in entries), Decimal("0")) == sum(
        (x.credit for x in entries), Decimal("0")
    )
    assert e.customer_balance("c1", "b1") == Decimal("0")
    assert any(x.account_id == "installment_interest" and x.credit == Decimal("5") for x in entries)
    assert payment.amount == Decimal("105")


def test_maintenance_delivery_with_parts_has_balanced_ledger():
    e = seed()
    e.transition_maintenance(ctx("status-1", {"maintenance.update"}), "missing", "READY") if False else None
    e.create_maintenance_ticket(ctx("m1", {"maintenance.create"}), "c1", "Phone", "Broken")
    e.transition_maintenance(ctx("m2", {"maintenance.update"}), "m1", "DIAGNOSING")
    e.transition_maintenance(ctx("m3", {"maintenance.update"}), "m1", "WAITING_CUSTOMER")
    e.transition_maintenance(ctx("m4", {"maintenance.update"}), "m1", "IN_PROGRESS")
    e.use_maintenance_part(ctx("part", {"maintenance.parts"}), "m1", "p1", Decimal("1"), Decimal("30"))
    e.transition_maintenance(ctx("m5", {"maintenance.update"}), "m1", "READY")
    e.deliver_maintenance(ctx("deliver", {"maintenance.update"}), "m1", Decimal("80"), Decimal("80"), "cash")
    entries = [x for x in e.ledger.all() if getattr(x, "reference_id", None) == "m1"]
    assert sum((x.debit for x in entries), Decimal("0")) == sum(
        (x.credit for x in entries), Decimal("0")
    )


def test_void_sale_reversal_is_balanced():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("sale-void-balanced", {"sales.create"}), None,
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("250")},),
        ({"wallet_id": "cash", "amount": Decimal("250")},),
    ))
    e.void_sale(ctx("void-balanced", {"sales.void"}), sale.id)
    entries = [x for x in e.ledger.all() if getattr(x, "reference_id", None) == sale.id]
    assert sum((x.debit for x in entries), Decimal("0")) == sum(
        (x.credit for x in entries), Decimal("0")
    )


def test_partial_return_reversal_is_balanced():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("sale-return-balanced", {"sales.create"}), None,
        ({"product_id": "p1", "quantity": 2, "unit_price": Decimal("250")},),
        ({"wallet_id": "cash", "amount": Decimal("500")},),
    ))
    e.return_sale(
        ctx("return-balanced", {"sales.return"}), sale.id,
        [{"sale_item_id": sale.items[0].id, "quantity": Decimal("1")}],
        "cash",
    )
    entries = [x for x in e.ledger.all() if getattr(x, "reference_id", None) == sale.id]
    assert sum((x.debit for x in entries), Decimal("0")) == sum(
        (x.credit for x in entries), Decimal("0")
    )
