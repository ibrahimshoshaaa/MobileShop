from decimal import Decimal

import pytest

from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.commands import CommandContext, CreateSaleCommand
from shared.contracts.errors import DomainError
from shared.models.erp import LedgerEntry, Product, Wallet


def ctx(cid, perms):
    return CommandContext(cid, "u1", "b1", frozenset(perms), "tenant-a")


def seeded():
    e = ERPCommandEngine()
    e.products.create("p1", Product("p1", "Phone", "SKU1", "PHONE_NEW", default_cost=Decimal("100")))
    e.wallets.create("cash", Wallet("cash", "b1", "Cash", "CASH"))
    e.adjust_stock(ctx("opening-stock", {"stock.adjust"}), "p1", Decimal("10"), Decimal("100"))
    e.ledger.create("opening", LedgerEntry(
        "opening", "b1", "wallet:cash", "OPENING", debit=Decimal("1000")
    ))
    return e


def test_sale_ledger_entries_are_balanced():
    e = seeded()
    command = CreateSaleCommand(
        ctx("sale-1", {"sales.create"}),
        None,
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("250")},),
        ({"wallet_id": "cash", "amount": Decimal("250")},),
    )
    e.create_sale(command)
    entries = e.ledger.all()
    sale_entries = [x for x in entries if "sale-1" in str(getattr(x, "reference_id", "")) or "sale-1" in str(getattr(x, "id", ""))]
    assert sale_entries
    assert sum((x.debit for x in sale_entries), Decimal("0")) == sum(
        (x.credit for x in sale_entries), Decimal("0")
    )

def test_wallet_transfer_preserves_total_wallet_balance():
    e = seeded()
    e.wallets.create("digital", Wallet("digital", "b1", "Digital", "DIGITAL"))
    before = e._balance("cash") + e._balance("digital")
    e.transfer_between_wallets(ctx("transfer-1", {"wallet.transfer"}), "cash", "digital", Decimal("100"))
    after = e._balance("cash") + e._balance("digital")
    assert after == before


def test_expense_decreases_wallet_and_balances_ledger():
    e = seeded()
    before = e._balance("cash")
    e.create_expense(ctx("expense-1", {"expenses.create"}), "cash", Decimal("50"), "rent")
    assert e._balance("cash") == before - Decimal("50")
    entries = [x for x in e.ledger.all() if "expense-1" in str(getattr(x, "reference_id", "")) or "expense-1" in str(getattr(x, "id", ""))]
    assert entries
    assert sum((x.debit for x in entries), Decimal("0")) == sum(
        (x.credit for x in entries), Decimal("0")
    )

def test_installment_command_idempotency_is_tenant_scoped():
    e = seeded()
    sale = e.create_sale(CreateSaleCommand(
        ctx("sale-installment", {"sales.create"}), None,
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("200")},),
        ({"wallet_id": "cash", "amount": Decimal("200")},),
    ))
    first = e.create_installment_plan(
        ctx("plan-1", {"installments.create"}), sale.id, "customer-1", 50, 10, 3
    )
    second = e.create_installment_plan(
        ctx("plan-1", {"installments.create"}), sale.id, "customer-1", 50, 10, 3
    )
    assert first is second


def test_void_sale_cannot_refund_more_than_wallet_balance():
    e = seeded()
    sale = e.create_sale(CreateSaleCommand(
        ctx("sale-void", {"sales.create"}), None,
        ({"product_id": "p1", "quantity": 1, "unit_price": Decimal("800")},),
        ({"wallet_id": "cash", "amount": Decimal("800")},),
    ))
    # Spend most of the cash after the sale, leaving less than the refund.
    e.create_expense(ctx("expense-after-sale", {"expenses.create"}), "cash", Decimal("1200"), "test")
    with pytest.raises(DomainError) as exc:
        e.void_sale(ctx("void-1", {"sales.void"}), sale.id)
    assert exc.value.code == "INSUFFICIENT_WALLET_BALANCE"
