"""Desktop maintenance repository.

Mirrors apps/admin_mobile/lib/features/maintenance/*.dart: same status state
machine as the backend's ERPCommandEngine._MAINT map, same use of the
inventory repository for parts stock (so a part used here decrements the
same product catalog the Inventory tab shows), and the same simplification
already documented for mobile — final_cost/payment are plain floats, not the
backend's Decimal-and-ledger-checked amounts.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone

import inventory_repo
from errors import AppError
from local_store import DEFAULT_BRANCH_ID, DEFAULT_TENANT_ID, get_store

TICKET_ENTITY = "maintenance_ticket"
PART_ENTITY = "maintenance_part"

# Mirrors ERPCommandEngine._MAINT exactly — each status can only advance to
# the one named here (no skipping steps); CANCELLED is reachable from any
# open status via cancel_ticket.
NEXT_STATUS = {
    "RECEIVED": "DIAGNOSING",
    "DIAGNOSING": "WAITING_CUSTOMER",
    "WAITING_CUSTOMER": "IN_PROGRESS",
    "IN_PROGRESS": "READY",
    "READY": "DELIVERED",
}

STATUS_LABELS = {
    "RECEIVED": "تم الاستلام",
    "DIAGNOSING": "جارِ الفحص",
    "WAITING_CUSTOMER": "بانتظار العميل",
    "IN_PROGRESS": "جارِ الإصلاح",
    "READY": "جاهز للتسليم",
    "DELIVERED": "تم التسليم",
    "CANCELLED": "ملغي",
}


@dataclass
class MaintenanceTicket:
    id: str
    customer_id: str
    customer_name: str
    device: str
    problem: str
    imei: str | None = None
    status: str = "RECEIVED"
    parts_cost: float = 0.0
    final_cost: float = 0.0
    payment: float = 0.0
    created_at: datetime | None = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def is_open(self) -> bool:
        return self.status not in ("DELIVERED", "CANCELLED")

    @property
    def next_status(self) -> str | None:
        return NEXT_STATUS.get(self.status)


@dataclass
class MaintenancePartUsage:
    id: str
    ticket_id: str
    product_id: str
    product_name: str
    quantity: int
    cost: float
    used_at: datetime | None = None

    def __post_init__(self):
        if self.used_at is None:
            self.used_at = datetime.now(timezone.utc)

    @property
    def total(self) -> float:
        return self.quantity * self.cost


def _ticket_to_payload(t: MaintenanceTicket) -> dict:
    return {
        "id": t.id, "customer_id": t.customer_id, "customer_name": t.customer_name, "device": t.device,
        "problem": t.problem, "imei": t.imei, "status": t.status, "parts_cost": t.parts_cost,
        "final_cost": t.final_cost, "payment": t.payment, "created_at": t.created_at.isoformat(),
    }


def _ticket_from_payload(m: dict) -> MaintenanceTicket:
    return MaintenanceTicket(
        id=m["id"], customer_id=m["customer_id"], customer_name=m["customer_name"], device=m["device"],
        problem=m["problem"], imei=m.get("imei"), status=m["status"], parts_cost=float(m["parts_cost"]),
        final_cost=float(m["final_cost"]), payment=float(m["payment"]), created_at=datetime.fromisoformat(m["created_at"]),
    )


def _part_to_payload(p: MaintenancePartUsage) -> dict:
    return {
        "id": p.id, "ticket_id": p.ticket_id, "product_id": p.product_id, "product_name": p.product_name,
        "quantity": p.quantity, "cost": p.cost, "used_at": p.used_at.isoformat(),
    }


def _part_from_payload(m: dict) -> MaintenancePartUsage:
    return MaintenancePartUsage(
        id=m["id"], ticket_id=m["ticket_id"], product_id=m["product_id"], product_name=m["product_name"],
        quantity=int(m["quantity"]), cost=float(m["cost"]), used_at=datetime.fromisoformat(m["used_at"]),
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def list_tickets() -> list[MaintenanceTicket]:
    store = get_store()
    rows = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=TICKET_ENTITY)
    return sorted((_ticket_from_payload(r["payload"]) for r in rows), key=lambda t: t.created_at, reverse=True)


def _get_ticket_row(ticket_id: str):
    store = get_store()
    row = store.get_record(entity=TICKET_ENTITY, record_id=ticket_id, tenant_id=DEFAULT_TENANT_ID)
    if row is None:
        raise AppError("طلب الصيانة غير موجود.")
    return row


def create_ticket(*, customer_id: str, customer_name: str, device: str, problem: str, imei: str | None = None) -> MaintenanceTicket:
    if not device.strip():
        raise AppError("يجب إدخال الجهاز.")
    if not problem.strip():
        raise AppError("يجب وصف المشكلة.")
    ticket = MaintenanceTicket(
        id=_new_id("mnt"), customer_id=customer_id, customer_name=customer_name, device=device.strip(),
        problem=problem.strip(), imei=(imei.strip() if imei and imei.strip() else None),
    )
    store = get_store()
    store.upsert_record(
        entity=TICKET_ENTITY, record_id=ticket.id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_ticket_to_payload(ticket), expected_version=0,
    )
    store.submit_command(
        command_id=_new_id("cmd-mnt-create"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="createMaintenanceTicket",
        payload={"customer_id": customer_id, "device": ticket.device, "problem": ticket.problem, "imei": ticket.imei},
    )
    return ticket


def advance_status(ticket_id: str) -> MaintenanceTicket:
    row = _get_ticket_row(ticket_id)
    ticket = _ticket_from_payload(row["payload"])
    next_status = ticket.next_status
    if next_status is None:
        raise AppError(f'لا يمكن نقل الحالة الحالية "{ticket.status_label}" لمرحلة تالية.')
    updated = replace(ticket, status=next_status)
    store = get_store()
    store.upsert_record(
        entity=TICKET_ENTITY, record_id=ticket_id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_ticket_to_payload(updated), expected_version=row["version"],
    )
    store.submit_command(
        command_id=_new_id("cmd-mnt-status"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="transitionMaintenance", payload={"ticket_id": ticket_id, "new_status": next_status},
    )
    return updated


def cancel_ticket(ticket_id: str) -> MaintenanceTicket:
    row = _get_ticket_row(ticket_id)
    ticket = _ticket_from_payload(row["payload"])
    if not ticket.is_open:
        raise AppError("طلب الصيانة مغلق بالفعل.")
    updated = replace(ticket, status="CANCELLED")
    store = get_store()
    store.upsert_record(
        entity=TICKET_ENTITY, record_id=ticket_id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_ticket_to_payload(updated), expected_version=row["version"],
    )
    store.submit_command(
        command_id=_new_id("cmd-mnt-cancel"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="cancelMaintenance", payload={"ticket_id": ticket_id},
    )
    return updated


def list_parts_used(ticket_id: str) -> list[MaintenancePartUsage]:
    store = get_store()
    rows = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=PART_ENTITY)
    parts = [_part_from_payload(r["payload"]) for r in rows if r["payload"]["ticket_id"] == ticket_id]
    return sorted(parts, key=lambda p: p.used_at)


def use_part(*, ticket_id: str, product_id: str, product_name: str, quantity: int, cost: float) -> MaintenancePartUsage:
    if quantity <= 0:
        raise AppError("الكمية يجب أن تكون أكبر من صفر.")
    row = _get_ticket_row(ticket_id)
    ticket = _ticket_from_payload(row["payload"])
    if not ticket.is_open:
        raise AppError("لا يمكن إضافة قطع لطلب مغلق.")

    # Decrement stock the same way Sales does — insufficient-stock check
    # happens inside adjust_stock itself.
    inventory_repo.adjust_stock(product_id, -quantity, f"استخدام في صيانة #{ticket_id}")

    usage = MaintenancePartUsage(id=_new_id("mntpart"), ticket_id=ticket_id, product_id=product_id,
                                  product_name=product_name, quantity=quantity, cost=cost)
    store = get_store()
    store.upsert_record(
        entity=PART_ENTITY, record_id=usage.id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_part_to_payload(usage), expected_version=0,
    )

    updated_ticket = replace(ticket, parts_cost=ticket.parts_cost + usage.total)
    store.upsert_record(
        entity=TICKET_ENTITY, record_id=ticket_id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_ticket_to_payload(updated_ticket), expected_version=row["version"],
    )
    store.submit_command(
        command_id=_new_id("cmd-mnt-part"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="useMaintenancePart",
        payload={"ticket_id": ticket_id, "product_id": product_id, "quantity": quantity, "cost": cost},
    )
    return usage


def deliver_ticket(*, ticket_id: str, final_price: float, payment: float, method: str) -> MaintenanceTicket:
    row = _get_ticket_row(ticket_id)
    ticket = _ticket_from_payload(row["payload"])
    if ticket.status != "READY":
        raise AppError('لا يمكن التسليم قبل أن تكون الحالة "جاهز للتسليم".')
    if final_price < 0 or payment < 0 or payment > final_price:
        raise AppError("قيمة الدفع غير صحيحة.")
    updated = replace(ticket, status="DELIVERED", final_cost=final_price, payment=payment)
    store = get_store()
    store.upsert_record(
        entity=TICKET_ENTITY, record_id=ticket_id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_ticket_to_payload(updated), expected_version=row["version"],
    )
    store.submit_command(
        command_id=_new_id("cmd-mnt-deliver"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="deliverMaintenanceTicket",
        payload={"ticket_id": ticket_id, "final_price": final_price, "payment": payment, "wallet_id": method},
    )
    return updated
