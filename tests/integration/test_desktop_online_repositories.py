from datetime import datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "desktop"))

import pytest

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "desktop"))

from apps.desktop import api_customers_repo, api_expenses_repo, api_installments_repo, api_maintenance_repo, api_suppliers_repo


class FakeClient:
    def __init__(self):
        self.branch_id = "LOCAL_BRANCH"
        self.calls = []
        self.command_result = None
        self.entities = {}

    def get_wallets(self, limit=100):
        return self.entities.get("wallets", [])

    def get_customers(self, limit=100):
        return self.entities.get("customers", [])

    def get_entity(self, entity, limit=100):
        return self.entities.get(entity, [])

    def command(self, command_id, command, payload):
        self.calls.append((command_id, command, payload))
        return self.command_result


def test_online_supplier_add_uses_command_not_local_storage(monkeypatch):
    fake = FakeClient()
    fake.command_result = {"id": "s1", "name": "Supplier", "phone": "0100", "active": True}
    monkeypatch.setattr(api_suppliers_repo, "_client", fake)

    supplier = api_suppliers_repo.add_supplier(name="Supplier", phone="0100")

    assert supplier.id == "s1"
    assert fake.calls[0][1] == "createSupplier"
    assert fake.calls[0][2] == {"name": "Supplier", "phone": "0100", "branch_ids": ["LOCAL_BRANCH"]}


def test_online_expense_resolves_wallet_and_posts_command(monkeypatch):
    fake = FakeClient()
    fake.entities["wallets"] = [{"id": "cash", "wallet_type": "CASH", "active": True}]
    fake.command_result = {
        "id": "e1", "amount": "25.00", "category": "rent",
        "wallet_id": "cash", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    monkeypatch.setattr(api_expenses_repo, "_client", fake)

    expense = api_expenses_repo.add_expense(amount=25, category="rent", method="CASH")

    assert expense.id == "e1"
    assert fake.calls[0][1] == "createExpense"
    assert fake.calls[0][2]["wallet_id"] == "cash"


def test_online_installment_plan_requires_linked_sale(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(api_installments_repo, "_client", fake)

    with pytest.raises(Exception, match="فاتورة"):
        api_installments_repo.create_plan(
            customer_id="c1", customer_name="Customer",
            price=100, down_payment=20, rate_percent=10, term_months=5,
        )


def test_online_installment_plan_sends_sale_and_down_payment_wallet(monkeypatch):
    fake = FakeClient()
    fake.entities["wallets"] = [{"id": "cash", "wallet_type": "CASH", "active": True}]
    fake.command_result = {
        "id": "p1", "sale_id": "sale1", "customer_id": "c1",
        "base_financed": "80.00", "rate_percent": "10", "increase": "8.00",
        "total_due": "88.00", "term_months": 5, "monthly_amount": "17.60",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    monkeypatch.setattr(api_installments_repo, "_client", fake)

    api_installments_repo.create_plan(
        customer_id="c1", customer_name="Customer",
        price=100, down_payment=20, rate_percent=10, term_months=5, sale_id="sale1",
    )

    assert fake.calls[0][1] == "createInstallmentPlan"
    assert fake.calls[0][2]["sale_id"] == "sale1"
    assert fake.calls[0][2]["down_payment_wallet_id"] == "cash"


def test_online_maintenance_zero_payment_does_not_require_wallet(monkeypatch):
    fake = FakeClient()
    fake.command_result = {
        "id": "m1", "customer_id": "c1", "device": "Phone", "problem": "Broken",
        "status": "DELIVERED", "parts_cost": "0.00", "final_cost": "100.00",
        "payment": "0.00", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    monkeypatch.setattr(api_maintenance_repo, "_client", fake)

    api_maintenance_repo.deliver_ticket(
        ticket_id="m1", final_price=100, payment=0, method="CASH",
    )

    assert fake.calls[0][1] == "deliverMaintenanceTicket"
    assert fake.calls[0][2]["wallet_id"] is None


def test_online_customer_update_uses_command(monkeypatch):
    fake = FakeClient()
    fake.command_result = {"id": "c1", "name": "Updated", "phone": "0111", "active": False}
    monkeypatch.setattr(api_customers_repo, "_client", fake)

    customer = api_customers_repo.Customer(id="c1", name="Updated", phone="0111", active=False)
    updated = api_customers_repo.update_customer(customer)

    assert updated.id == "c1"
    assert fake.calls[0][1] == "updateCustomer"
    assert fake.calls[0][2] == {
        "customer_id": "c1",
        "changes": {"name": "Updated", "phone": "0111", "active": False},
    }


def test_online_supplier_update_uses_command(monkeypatch):
    fake = FakeClient()
    fake.command_result = {"id": "s1", "name": "Updated", "phone": "0111", "active": False}
    monkeypatch.setattr(api_suppliers_repo, "_client", fake)

    supplier = api_suppliers_repo.Supplier(id="s1", name="Updated", phone="0111", active=False)
    updated = api_suppliers_repo.update_supplier(supplier)

    assert updated.id == "s1"
    assert fake.calls[0][1] == "updateSupplier"
    assert fake.calls[0][2] == {
        "supplier_id": "s1",
        "changes": {"name": "Updated", "phone": "0111", "active": False},
    }


def test_online_maintenance_delivery_uses_injected_repo():
    from apps.desktop.maintenance_tab import DeliverDialog

    class DummyVar:
        def __init__(self, value):
            self.value = value
        def get(self):
            return self.value

    class DummyLabel:
        def config(self, **kwargs):
            raise AssertionError(kwargs)

    class FakeRepo:
        def __init__(self):
            self.calls = []
        def deliver_ticket(self, **kwargs):
            self.calls.append(kwargs)

    class DummyDialog:
        def __init__(self):
            self.ticket = type("Ticket", (), {"id": "m1"})()
            self.repo = FakeRepo()
            self.price_var = DummyVar("100")
            self.payment_var = DummyVar("50")
            self.method_var = DummyVar("نقدي")
            self.error_label = DummyLabel()
            self.destroyed = False
        def destroy(self):
            self.destroyed = True

    dummy = DummyDialog()
    original_methods = __import__("apps.desktop.maintenance_tab", fromlist=["sales_repo"]).sales_repo.PAYMENT_METHODS
    expected_code = next(code for code, label in original_methods if label == "نقدي")
    DeliverDialog._submit(dummy)

    assert dummy.repo.calls == [{
        "ticket_id": "m1",
        "final_price": 100.0,
        "payment": 50.0,
        "method": expected_code,
    }]
    assert dummy.destroyed is True
