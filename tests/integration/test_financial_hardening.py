from decimal import Decimal
from datetime import date

import pytest

from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.commands import CommandContext, CreateSaleCommand
from shared.contracts.errors import DomainError
from shared.models.erp import (
    Customer, Employee, LedgerEntry, Product, Supplier, Wallet,
)


def ctx(cid, perms, branch="b1", tenant="tenant-a"):
    return CommandContext(cid, "u1", branch, frozenset(perms), "default")


def base_engine():
    e = ERPCommandEngine()
    e.products.create("p1", Product("p1", "Phone", "SKU1", "PHONE_NEW", default_cost=Decimal("100")))
    e.wallets.create("cash", Wallet("cash", "b1", "Cash", "CASH"))
    e.wallets.create("digital", Wallet("digital", "b1", "Digital", "DIGITAL"))
    e.ledger.create("opening", LedgerEntry("opening", "b1", "wallet:cash", "OPENING", debit=Decimal("6000")))
    return e


def test_wallet_transfer_commission_is_fully_balanced_and_idempotent():
    e = base_engine()
    first = e.transfer_between_wallets(ctx("wt-1", {"wallet.transfer"}), "cash", "digital", Decimal("100"))
    second = e.transfer_between_wallets(ctx("wt-1", {"wallet.transfer"}), "cash", "digital", Decimal("100"))
    assert first == second == "wt-1"
    assert e._balance("cash") == Decimal("1899.00")
    assert e._balance("digital") == Decimal("100.00")
    rows = [x for x in e.ledger.all() if x.reference_id == "wt-1"]
    assert sum((x.debit for x in rows), Decimal("0")) == Decimal("100.00")
    assert sum((x.credit for x in rows), Decimal("0")) == Decimal("102.00")
    assert any(x.account_id == "transfer_commission" and x.credit == Decimal("1.00") for x in rows)


def test_salary_cannot_be_paid_twice_and_is_idempotent_at_calculation():
    e = base_engine()
    e.employees.create("emp", Employee("emp", "Worker", branch_ids=("b1",)))
    first = e.calculate_salary(ctx("salary-calc", {"employees.salary"}), "emp", "2026-09", 5000)
    second = e.calculate_salary(ctx("salary-calc", {"employees.salary"}), "emp", "2026-09", 5000)
    assert first is second
    paid = e.pay_salary(ctx("salary-pay", {"employees.salary"}), first.id, "cash")
    assert paid.paid == Decimal("5000.00")
    with pytest.raises(DomainError) as exc:
        e.pay_salary(ctx("salary-pay-2", {"employees.salary"}), first.id, "cash")
    assert exc.value.code == "INVALID_INPUT"


def test_supplier_payment_cannot_exceed_payable_and_is_idempotent():
    e = base_engine()
    e.suppliers.create("sup", Supplier("sup", "Supplier", branch_ids=("b1",)))
    e.ledger.create("payable", LedgerEntry("payable", "b1", "payable:sup", "PURCHASE_PAYABLE", credit=Decimal("500")))
    first = e.pay_supplier(ctx("sup-pay", {"purchases.pay_supplier"}), "sup", "cash", Decimal("300"))
    second = e.pay_supplier(ctx("sup-pay", {"purchases.pay_supplier"}), "sup", "cash", Decimal("300"))
    assert first is second
    assert e.supplier_balance("sup", "b1") == Decimal("200.00")
    with pytest.raises(DomainError) as exc:
        e.pay_supplier(ctx("sup-pay-2", {"purchases.pay_supplier"}), "sup", "cash", Decimal("201"))
    assert exc.value.code == "INVALID_PAYMENT"


def test_maintenance_cancel_is_branch_scoped_and_terminal_safe():
    e = base_engine()
    e.customers.create("c1", Customer("c1", "Customer"))
    ticket = e.create_maintenance_ticket(ctx("m1", {"maintenance.create"}), "c1", "Phone", "Broken")
    with pytest.raises(DomainError) as exc:
        e.cancel_maintenance(ctx("m2", {"maintenance.update"}, branch="b2"), ticket.id)
    assert exc.value.code == "BRANCH_ACCESS_DENIED"
    e.cancel_maintenance(ctx("m3", {"maintenance.update"}), ticket.id)
    with pytest.raises(DomainError) as exc:
        e.cancel_maintenance(ctx("m4", {"maintenance.update"}), ticket.id)
    assert exc.value.code == "INVALID_INPUT"


def test_installment_rejects_voided_sale():
    e = base_engine()
    e.customers.create("c1", Customer("c1", "Customer"))
    e.products.create("p2", Product("p2", "Phone 2", "SKU2", "PHONE_NEW", default_cost=Decimal("100")))
    e.adjust_stock(ctx("stock", {"stock.adjust"}), "p2", Decimal("1"), Decimal("100"))
    sale = e.create_sale(CreateSaleCommand(
        ctx("sale", {"sales.create"}), "c1",
        ({"product_id": "p2", "quantity": 1, "unit_price": Decimal("200")},),
        ({"wallet_id": "cash", "amount": Decimal("200")},),
    ))
    e.void_sale(ctx("void", {"sales.void"}), sale.id)
    with pytest.raises(DomainError) as exc:
        e.create_installment_plan(ctx("plan", {"installments.create"}), sale.id, "c1", 0, 10, 3)
    assert exc.value.code == "INVALID_INPUT"
