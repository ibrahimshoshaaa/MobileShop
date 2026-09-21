from __future__ import annotations

import uuid
from dataclasses import dataclass

from api_client import ApiClient
from errors import AppError


@dataclass
class Customer:
    id: str
    name: str
    phone: str | None
    active: bool = True


_client = ApiClient()


def _to_customer(payload: dict) -> Customer:
    return Customer(
        id=payload["id"],
        name=payload["name"],
        phone=payload.get("phone"),
        active=bool(payload.get("active", True)),
    )


def list_customers(query: str = "") -> list[Customer]:
    rows = [_to_customer(row) for row in _client.get_customers()]
    q = query.strip().lower()
    if q:
        rows = [c for c in rows if q in c.name.lower() or (c.phone and q in c.phone)]
    return sorted(rows, key=lambda c: c.name)


def get_customer(customer_id: str) -> Customer | None:
    return next((c for c in list_customers() if c.id == customer_id), None)


def add_customer(*, name: str, phone: str | None) -> Customer:
    if not name.strip():
        raise AppError("اسم العميل مطلوب.")
    data = _client.command(
        f"cmd-create-customer-{uuid.uuid4().hex[:12]}",
        "createCustomer",
        {"name": name.strip(), "phone": phone.strip() if phone and phone.strip() else None},
    )
    return _to_customer(data)


def update_customer(customer: Customer) -> Customer:
    if not customer.name.strip():
        raise AppError("اسم العميل مطلوب.")
    data = _client.command(
        f"cmd-update-customer-{uuid.uuid4().hex[:12]}",
        "updateCustomer",
        {"customer_id": customer.id, "changes": {
            "name": customer.name.strip(),
            "phone": customer.phone.strip() if customer.phone and customer.phone.strip() else None,
            "active": customer.active,
        }},
    )
    return _to_customer(data)
