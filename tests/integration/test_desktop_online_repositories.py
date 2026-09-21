from datetime import datetime, timezone

import pytest

from apps.desktop import api_expenses_repo, api_installments_repo, api_maintenance_repo, api_suppliers_repo


class FakeClient:
    def __init__(self):
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
    assert fake.calls[0][2] == {"name": "Supplier", "phone": "0100"}


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
