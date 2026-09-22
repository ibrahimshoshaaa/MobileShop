import json
from decimal import Decimal
from datetime import date

from backend.functions.persistence.domain_serializer import deserialize_value, serialize_value
from shared.models.erp import (
    Customer, DailyClosing, Employee, Expense, InstallmentPayment, InstallmentPlan,
    LedgerEntry, MaintenanceTicket, Payment, Product, ProductUnit, Purchase, PurchaseItem,
    SalaryRecord, Sale, SaleItem, StockMovement, Supplier, Wallet,
)


def roundtrip(value):
    """Serialize -> JSON string -> parse -> deserialize, exactly the path
    the durable engine's SQLite storage takes."""
    return deserialize_value(json.loads(json.dumps(serialize_value(value))))


def test_simple_dataclass_roundtrip():
    p = Product(id="p1", name="شاحن", sku="SKU-1", product_type="ACCESSORY", selling_price=Decimal("99.99"))
    assert roundtrip(p) == p


def test_dataclass_with_nested_tuple_of_dataclasses():
    item = SaleItem(id="i1", product_id="p1", quantity=Decimal("2"), unit_price=Decimal("50"))
    payment = Payment(id="pay1", sale_id="s1", wallet_id="w1", amount=Decimal("100"))
    sale = Sale(id="s1", branch_id="b1", customer_id=None, items=(item,), subtotal=Decimal("100"),
                discount=Decimal("0"), total=Decimal("100"), payments=(payment,))
    restored = roundtrip(sale)
    assert restored == sale
    assert isinstance(restored.items, tuple) and isinstance(restored.items[0], SaleItem)
    assert isinstance(restored.payments[0], Payment)


def test_dataclass_with_nested_purchase_items():
    pi = PurchaseItem(id="pi1", product_id="p1", quantity=Decimal("3"), unit_cost=Decimal("10"))
    purchase = Purchase(id="pu1", branch_id="b1", supplier_id="sup1", items=(pi,), total=Decimal("30"))
    restored = roundtrip(purchase)
    assert restored == purchase
    assert isinstance(restored.items[0], PurchaseItem)


def test_dict_with_decimal_values_and_dates():
    closing = DailyClosing(
        id="c1", branch_id="b1", closing_date=date(2026, 9, 18),
        expected={"w1": Decimal("100.50")}, actual={"w1": Decimal("100.00")},
        discrepancy={"w1": Decimal("-0.50")},
    )
    restored = roundtrip(closing)
    assert restored == closing
    assert isinstance(restored.closing_date, date)
    assert isinstance(restored.expected["w1"], Decimal)


def test_plain_dict_roundtrip():
    obj = {"id": "t1", "type": "EXCHANGE", "amount": Decimal("42.5"), "commission": Decimal("1")}
    restored = roundtrip(obj)
    assert restored == obj
    assert isinstance(restored, dict)


def test_frozenset_roundtrip():
    perms = frozenset({"sales.create", "products.edit"})
    restored = roundtrip(perms)
    assert restored == perms
    assert isinstance(restored, frozenset)


def test_all_other_domain_types_roundtrip():
    values = [
        Customer(id="c1", name="أحمد", phone="0100"),
        Supplier(id="s1", name="مورد", branch_ids=("b1", "b2")),
        Wallet(id="w1", branch_id="b1", name="نقدي", wallet_type="CASH"),
        LedgerEntry(id="l1", branch_id="b1", account_id="wallet:w1", entry_type="SALE", debit=Decimal("10")),
        Expense(id="e1", branch_id="b1", wallet_id="w1", amount=Decimal("5"), category="rent"),
        InstallmentPlan(id="i1", sale_id="s1", customer_id="c1", base_financed=Decimal("100"),
                         rate_percent=Decimal("10"), increase=Decimal("10"), total_due=Decimal("110"),
                         term_months=2, monthly_amount=Decimal("55")),
        InstallmentPayment(id="ip1", plan_id="i1", amount=Decimal("55"), wallet_id="w1"),
        MaintenanceTicket(id="m1", branch_id="b1", customer_id="c1", device="iPhone", imei=None, problem="شاشة"),
        Employee(id="emp1", name="سارة", branch_ids=("b1",), fixed_salary=Decimal("3000")),
        SalaryRecord(id="sal1", employee_id="emp1", period="2026-09", base=Decimal("3000")),
        StockMovement(id="st1", branch_id="b1", product_id="p1", quantity=Decimal("5"),
                      movement_type="ADJUSTMENT", reference_id="r1"),
        ProductUnit(id="u1", product_id="p1", branch_id="b1", imei1="123", final_cost=Decimal("100")),
    ]
    for v in values:
        assert roundtrip(v) == v, f"roundtrip failed for {type(v).__name__}"
