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
    e.wallets.create("digital", Wallet("digital", "b1", "Digital", "DIGITAL"))
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
    assert e.ledger_transaction_totals(sale.id) == (Decimal("380.00"), Decimal("380.00"))



def test_split_payment_full_return_refunds_original_wallets():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("split-sale", {"sales.create"}), None,
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("100")},),
        (
            {"wallet_id": "cash", "amount": Decimal("60")},
            {"wallet_id": "digital", "amount": Decimal("40")},
        ),
    ))
    returned = e.return_sale(
        ctx("split-return", {"sales.return"}), sale.id,
        [{"sale_item_id": sale.items[0].id, "quantity": Decimal("1")}],
    )
    assert returned["amount"] == Decimal("100.00")
    assert returned["refund_allocations"] == (("cash", Decimal("60.00")), ("digital", Decimal("40.00")))
    assert e.customer_balance("c1", "b1") == Decimal("0.00")


def test_mixed_paid_credit_full_return_refunds_paid_part_and_clears_receivable():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("mixed-sale", {"sales.create"}), "c1",
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("100")},),
        ({"wallet_id": "cash", "amount": Decimal("60")},),
    ))
    e.return_sale(
        ctx("mixed-return", {"sales.return"}), sale.id,
        [{"sale_item_id": sale.items[0].id, "quantity": Decimal("1")}],
    )
    assert e._balance("cash") == Decimal("5000.00")
    assert e.customer_balance("c1", "b1") == Decimal("0.00")

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
    assert e.ledger_transaction_totals(sale.id) == (Decimal("580.00"), Decimal("580.00"))


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




def test_day_close_blocks_financial_commands_until_reopened():
    e = seed()
    e.close_day(ctx("close", {"closing.close"}), date.today(), {"cash": Decimal("5000"), "digital": Decimal("0")})
    with pytest.raises(DomainError) as exc:
        e.create_expense(ctx("blocked", {"expenses.create"}), "cash", Decimal("10"), "rent")
    assert exc.value.code == "DAY_CLOSED"
    e.reopen_day(ctx("reopen", {"closing.reopen"}), date.today())
    e.create_expense(ctx("after-reopen", {"expenses.create"}), "cash", Decimal("10"), "rent")


def test_future_day_cannot_be_closed():
    e = seed()
    with pytest.raises(DomainError) as exc:
        e.close_day(
            ctx("future-close", {"closing.close"}),
            date.today().replace(year=date.today().year + 1),
            {"cash": Decimal("5000"), "digital": Decimal("0")},
        )
    assert exc.value.code == "INVALID_INPUT"

def test_disabled_wallet_cannot_be_used_for_financial_operations():
    e = seed()
    e.wallets.create("disabled", Wallet("disabled", "b1", "Disabled", "CASH", active=False))
    with pytest.raises(DomainError) as exc:
        e.create_expense(ctx("disabled-expense", {"expenses.create"}), "disabled", Decimal("10"), "test")
    assert exc.value.code == "WALLET_DISABLED"


def test_sale_cannot_have_two_installment_plans():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("installment-sale", {"sales.create"}), "c1",
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("200")},),
        (),
    ))
    e.create_installment_plan(
        ctx("plan-a", {"installments.create"}), sale.id, "c1",
        Decimal("0"), Decimal("10"), 2,
    )
    with pytest.raises(DomainError) as exc:
        e.create_installment_plan(
            ctx("plan-b", {"installments.create"}), sale.id, "c1",
            Decimal("0"), Decimal("10"), 2,
        )
    assert exc.value.code == "INSTALLMENT_ALREADY_EXISTS"

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


def test_maintenance_part_usage_is_branch_scoped_and_validated():
    e = seed()
    ticket = e.create_maintenance_ticket(
        ctx("maintenance-branch", {"maintenance.create"}), "c1", "Phone", "Broken"
    )
    foreign = CommandContext(
        "foreign-part", "u1", "b2", frozenset({"maintenance.parts"}), "tenant-a"
    )
    with pytest.raises(DomainError) as exc:
        e.use_maintenance_part(foreign, ticket.id, "p1", Decimal("1"), Decimal("100"))
    assert exc.value.code == "BRANCH_ACCESS_DENIED"


def test_single_return_command_cannot_repeat_same_sale_item():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("duplicate-return-sale", {"sales.create"}), None,
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("100")},),
        ({"wallet_id": "cash", "amount": Decimal("100")},),
    ))
    with pytest.raises(DomainError) as exc:
        e.return_sale(
            ctx("duplicate-return", {"sales.return"}), sale.id,
            [
                {"sale_item_id": sale.items[0].id, "quantity": Decimal("1")},
                {"sale_item_id": sale.items[0].id, "quantity": Decimal("1")},
            ],
            "cash",
        )
    assert exc.value.code == "INVALID_RETURN"


def test_sale_cannot_be_voided_after_a_return():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("void-return-sale", {"sales.create"}), None,
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("100")},),
        ({"wallet_id": "cash", "amount": Decimal("100")},),
    ))
    e.return_sale(
        ctx("void-return", {"sales.return"}), sale.id,
        [{"sale_item_id": sale.items[0].id, "quantity": Decimal("1")}],
        "cash",
    )
    with pytest.raises(DomainError) as exc:
        e.void_sale(ctx("void-after-return", {"sales.void"}), sale.id)
    assert exc.value.code == "INVALID_VOID"

def test_installment_down_payment_cannot_overdraw_wallet():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("credit-overdraw", {"sales.create"}), "c1",
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("200")},), (),
    ))
    with pytest.raises(DomainError) as exc:
        e.create_installment_plan(
            ctx("plan-overdraw", {"installments.create"}), sale.id, "c1",
            Decimal("100"), Decimal("10"), 2, down_payment_wallet_id="cash",
        )
    assert exc.value.code == "INSUFFICIENT_WALLET_BALANCE"


def test_installment_collection_cannot_overdraw_wallet():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("credit-collect-overdraw", {"sales.create"}), "c1",
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("200")},), (),
    ))
    plan = e.create_installment_plan(
        ctx("collect-plan-overdraw", {"installments.create"}), sale.id, "c1",
        Decimal("0"), Decimal("10"), 2,
    )
    with pytest.raises(DomainError) as exc:
        e.collect_installment(
            ctx("collect-overdraw", {"installments.collect"}), plan.id, Decimal("5000"), "cash",
        )
    assert exc.value.code == "INSUFFICIENT_WALLET_BALANCE"

def test_customer_transfer_moves_value_in_correct_direction_and_balances():
    e = seed()
    e.ledger.create("digital-opening", LedgerEntry(
        "digital-opening", "b1", "wallet:digital", "OPENING", debit=Decimal("1000")
    ))
    e.transfer_customer(
        ctx("cash-to-digital", {"transfer.create"}), "cash", "digital", Decimal("100"), Decimal("1"),
    )
    assert e._balance("cash") == Decimal("5101.00")
    assert e._balance("digital") == Decimal("900.00")
    assert e.ledger_transaction_totals("cash-to-digital") == (Decimal("101.00"), Decimal("101.00"))
    e.transfer_customer(
        ctx("digital-to-cash", {"transfer.create"}), "digital", "cash", Decimal("100"), Decimal("1"),
    )
    assert e._balance("digital") == Decimal("1000.00")
    assert e._balance("cash") == Decimal("5000.00")
    assert e.ledger_transaction_totals("digital-to-cash") == (Decimal("101.00"), Decimal("101.00"))

def test_product_update_rejects_immutable_or_duplicate_fields():
    e = seed()
    e.products.create("p2", Product("p2", "Other", "SKU2", "PHONE_NEW"))
    with pytest.raises(DomainError) as exc:
        e.update_product(ctx("bad-product-field", {"products.edit"}), "p1", id="evil")
    assert exc.value.code == "INVALID_INPUT"
    with pytest.raises(DomainError) as exc:
        e.update_product(ctx("duplicate-sku", {"products.edit"}), "p1", sku="SKU2")
    assert exc.value.code == "DUPLICATE_PRODUCT"


def test_exchange_is_atomic_when_new_sale_fails():
    e = seed()
    sale = e.create_sale(CreateSaleCommand(
        ctx("exchange-old", {"sales.create"}), None,
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("100")},),
        ({"wallet_id": "cash", "amount": Decimal("100")},),
    ))
    before_cash=e._balance("cash")
    before_stock=e._available_qty("b1","p1")
    with pytest.raises(DomainError):
        e.exchange_sale(
            ctx("exchange", {"sales.return", "sales.create"}),
            sale.id,
            [{"sale_item_id": sale.items[0].id, "quantity": Decimal("1")}],
            [{"product_id": "missing", "quantity": Decimal("1"), "unit_price": Decimal("100")}],
            (),
        )
    assert e._balance("cash")==before_cash
    assert e._available_qty("b1","p1")==before_stock
    assert e.returns.all()==[]


def test_stock_transfer_rejects_unknown_or_inactive_destination_branch():
    e = seed()
    with pytest.raises(DomainError) as exc:
        e.transfer_stock(
            ctx("transfer-unknown-branch", {"stock.transfer"}),
            "p1", Decimal("1"), "b1", "missing", Decimal("100"),
        )
    assert exc.value.code == "BRANCH_ACCESS_DENIED"
