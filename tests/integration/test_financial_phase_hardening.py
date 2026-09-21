from decimal import Decimal
from datetime import date

import pytest

from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.commands import CommandContext, CreateSaleCommand
from shared.contracts.errors import DomainError
from shared.models.erp import Customer, LedgerEntry, Product, Wallet


def ctx(cid, perms):
    return CommandContext(cid, "u1", "b1", frozenset(perms), "tenant-a")


def seed():
    e = ERPCommandEngine()
    e.products.create("p1", Product("p1", "Phone", "SKU1", "PHONE_NEW", default_cost=Decimal("100")))
    e.wallets.create("cash", Wallet("cash", "b1", "Cash", "CASH"))
    e.ledger.create("opening", LedgerEntry(
        "opening", "b1", "wallet:cash", "OPENING", debit=Decimal("5000")
    ))
    e.customers.create("c1", Customer("c1", "Customer"))
    e.adjust_stock(ctx("stock", {"stock.adjust"}), "p1", Decimal("5"), Decimal("100"))
    return e


def test_discounted_full_return_refunds_net_invoice_total():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("sale", {"sales.create", "sales.discount"}), None,
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("100")},),
        ({"wallet_id": "cash", "amount": Decimal("90")},),
        Decimal("10"),
    ))
    returned = e.return_sale(
        ctx("return", {"sales.return"}), sale.id,
        [{"sale_item_id": sale.items[0].id, "quantity": Decimal("1")}],
        "cash",
    )
    assert returned["amount"] == Decimal("90.00")
    assert e.ledger_transaction_totals(sale.id) == (Decimal("190.00"), Decimal("190.00"))


def test_partial_discounted_returns_never_exceed_invoice_total():
    e = seed()
    e.products.update("p1", Product("p1", "Phone", "SKU1", "PHONE_NEW", default_cost=Decimal("100")))
    e.adjust_stock(ctx("stock2", {"stock.adjust"}), "p1", Decimal("1"), Decimal("100"))
    sale = e.create_sale(CreateSaleCommand(
        ctx("sale2", {"sales.create", "sales.discount"}), None,
        ({"product_id": "p1", "quantity": 2, "unit_price": Decimal("50")},),
        ({"wallet_id": "cash", "amount": Decimal("90")},),
        Decimal("10"),
    ))
    first = e.return_sale(
        ctx("return1", {"sales.return"}), sale.id,
        [{"sale_item_id": sale.items[0].id, "quantity": Decimal("1")}],
        "cash",
    )
    second = e.return_sale(
        ctx("return2", {"sales.return"}), sale.id,
        [{"sale_item_id": sale.items[0].id, "quantity": Decimal("1")}],
        "cash",
    )
    assert first["amount"] + second["amount"] == Decimal("90.00")
    assert e.ledger_transaction_totals(sale.id) == (Decimal("190.00"), Decimal("190.00"))


def test_partial_maintenance_payment_creates_customer_receivable():
    e = seed()
    ticket = e.create_maintenance_ticket(
        ctx("maintenance", {"maintenance.create"}), "c1", "Phone", "Broken"
    )
    for i, status in enumerate(["DIAGNOSING", "WAITING_CUSTOMER", "IN_PROGRESS", "READY"]):
        ticket = e.transition_maintenance(
            ctx(f"maintenance-{i}", {"maintenance.update"}), ticket.id, status
        )
    delivered = e.deliver_maintenance(
        ctx("deliver", {"maintenance.update"}), ticket.id, Decimal("120"), Decimal("70"), "cash"
    )
    assert delivered.payment == Decimal("70.00")
    assert e.customer_balance("c1", "b1") == Decimal("50.00")
    assert e.ledger_transaction_totals(ticket.id) == (Decimal("120.00"), Decimal("120.00"))


def test_installment_down_payment_clears_existing_receivable():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("credit-sale", {"sales.create"}), "c1",
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("200")},),
        (),
    ))
    plan = e.create_installment_plan(
        ctx("plan", {"installments.create"}), sale.id, "c1",
        Decimal("50"), Decimal("10"), 2, down_payment_wallet_id="cash"
    )
    assert plan.base_financed == Decimal("150.00")
    assert e.customer_balance("c1", "b1") == Decimal("150.00")
    assert e._balance("cash") == Decimal("5050.00")
    e.collect_installment(ctx("collect", {"installments.collect"}), plan.id, Decimal("165"), "cash")
    assert e.customer_balance("c1", "b1") == Decimal("0.00")
    assert e.ledger_transaction_totals(plan.id) == (Decimal("215.00"), Decimal("215.00"))


def test_financial_command_rolls_back_all_state_on_late_failure():
    e = seed()
    before_cash = e._balance("cash")
    before_stock = e._available_qty("b1", "p1")
    with pytest.raises(RuntimeError):
        e.transaction(lambda: (
            e.create_expense(ctx("rollback-expense", {"expenses.create"}), "cash", Decimal("50"), "test"),
            (_ for _ in ()).throw(RuntimeError("late failure")),
        ))
    assert e._balance("cash") == before_cash
    assert e._available_qty("b1", "p1") == before_stock
    assert e.expenses.all() == []
    assert e.ledger.all() == [e.ledger.get("opening")]
