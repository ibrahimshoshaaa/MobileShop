from __future__ import annotations

import uuid
from dataclasses import dataclass

from errors import AppError
from local_store import DEFAULT_BRANCH_ID, DEFAULT_TENANT_ID, get_store

ENTITY = "customer"


@dataclass
class Customer:
    id: str
    name: str
    phone: str | None
    active: bool = True


def _to_customer(payload: dict) -> Customer:
    return Customer(
        id=payload["id"],
        name=payload["name"],
        phone=payload.get("phone"),
        active=bool(payload.get("active", True)),
    )


def _to_payload(c: Customer) -> dict:
    return {"id": c.id, "name": c.name, "phone": c.phone, "active": c.active}


def _new_id() -> str:
    return f"cust-{uuid.uuid4().hex[:12]}"


def list_customers(query: str = "") -> list[Customer]:
    store = get_store()
    rows = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=ENTITY)
    customers = [_to_customer(r["payload"]) for r in rows]
    q = query.strip().lower()
    if not q:
        return sorted(customers, key=lambda c: c.name)
    return sorted(
        [c for c in customers if q in c.name.lower() or (c.phone and q in c.phone)],
        key=lambda c: c.name,
    )


def get_customer(customer_id: str) -> Customer | None:
    store = get_store()
    row = store.get_record(entity=ENTITY, record_id=customer_id, tenant_id=DEFAULT_TENANT_ID)
    return _to_customer(row["payload"]) if row else None


def add_customer(*, name: str, phone: str | None) -> Customer:
    if not name.strip():
        raise AppError("اسم العميل مطلوب.")
    clean_phone = phone.strip() if phone and phone.strip() else None
    if clean_phone and any(c.phone == clean_phone for c in list_customers()):
        raise AppError("يوجد عميل آخر بنفس رقم الهاتف.")
    customer = Customer(id=_new_id(), name=name.strip(), phone=clean_phone)
    store = get_store()
    store.upsert_record(
        entity=ENTITY, record_id=customer.id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(customer), expected_version=0,
    )
    store.submit_command(
        command_id=f"cmd-create-customer-{uuid.uuid4().hex[:12]}", tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, command="createCustomer", payload=_to_payload(customer),
    )
    return customer


def update_customer(customer: Customer) -> Customer:
    store = get_store()
    current = store.get_record(entity=ENTITY, record_id=customer.id, tenant_id=DEFAULT_TENANT_ID)
    if current is None:
        raise AppError("العميل غير موجود.")
    if not customer.name.strip():
        raise AppError("اسم العميل مطلوب.")
    if customer.phone and any(c.phone == customer.phone for c in list_customers() if c.id != customer.id):
        raise AppError("يوجد عميل آخر بنفس رقم الهاتف.")
    try:
        store.upsert_record(
            entity=ENTITY, record_id=customer.id, tenant_id=DEFAULT_TENANT_ID,
            branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(customer), expected_version=current["version"],
        )
    except ValueError as e:
        if str(e) == "STALE_VERSION":
            raise AppError("تعذّر الحفظ: تم تعديل هذا العميل من جهاز آخر في نفس الوقت.") from e
        raise
    store.submit_command(
        command_id=f"cmd-update-customer-{uuid.uuid4().hex[:12]}", tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, command="updateCustomer", payload=_to_payload(customer),
    )
    return customer
