"""Desktop suppliers repository.

Deviation from shared/models/erp.py Supplier: branch_ids is omitted, same
reasoning as on mobile — no branch-selection UI exists anywhere in this app
yet, so tracking per-branch association would just be dead weight.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from errors import AppError
from local_store import DEFAULT_BRANCH_ID, DEFAULT_TENANT_ID, get_store

ENTITY = "supplier"


@dataclass
class Supplier:
    id: str
    name: str
    phone: str | None
    active: bool = True


def _to_supplier(payload: dict) -> Supplier:
    return Supplier(id=payload["id"], name=payload["name"], phone=payload.get("phone"), active=bool(payload.get("active", True)))


def _to_payload(s: Supplier) -> dict:
    return {"id": s.id, "name": s.name, "phone": s.phone, "active": s.active}


def _new_id() -> str:
    return f"sup-{uuid.uuid4().hex[:12]}"


def list_suppliers(query: str = "") -> list[Supplier]:
    store = get_store()
    rows = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=ENTITY)
    suppliers = [_to_supplier(r["payload"]) for r in rows]
    q = query.strip().lower()
    if q:
        suppliers = [s for s in suppliers if q in s.name.lower() or (s.phone and q in s.phone)]
    return sorted(suppliers, key=lambda s: s.name)


def add_supplier(*, name: str, phone: str | None) -> Supplier:
    if not name.strip():
        raise AppError("اسم المورد مطلوب.")
    clean_phone = phone.strip() if phone and phone.strip() else None
    if clean_phone and any(s.phone == clean_phone for s in list_suppliers()):
        raise AppError("يوجد مورد آخر بنفس رقم الهاتف.")
    supplier = Supplier(id=_new_id(), name=name.strip(), phone=clean_phone)
    store = get_store()
    store.upsert_record(
        entity=ENTITY, record_id=supplier.id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(supplier), expected_version=0,
    )
    store.submit_command(
        command_id=f"cmd-create-supplier-{uuid.uuid4().hex[:12]}", tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, command="createSupplier", payload=_to_payload(supplier),
    )
    return supplier


def update_supplier(supplier: Supplier) -> Supplier:
    # Note: no 'updateSupplier' command exists in the backend's dispatch
    # table yet (only 'createSupplier' does), so this only updates local
    # state and isn't queued for sync yet — same gap as on mobile.
    store = get_store()
    current = store.get_record(entity=ENTITY, record_id=supplier.id, tenant_id=DEFAULT_TENANT_ID)
    if current is None:
        raise AppError("المورد غير موجود.")
    if not supplier.name.strip():
        raise AppError("اسم المورد مطلوب.")
    if supplier.phone and any(s.phone == supplier.phone for s in list_suppliers() if s.id != supplier.id):
        raise AppError("يوجد مورد آخر بنفس رقم الهاتف.")
    try:
        store.upsert_record(
            entity=ENTITY, record_id=supplier.id, tenant_id=DEFAULT_TENANT_ID,
            branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(supplier), expected_version=current["version"],
        )
    except ValueError as e:
        if str(e) == "STALE_VERSION":
            raise AppError("تعذّر الحفظ: تم تعديل هذا المورد من جهاز آخر في نفس الوقت.") from e
        raise
    return supplier
