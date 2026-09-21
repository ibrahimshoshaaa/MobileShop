from __future__ import annotations
import uuid
from dataclasses import dataclass
from api_client import ApiClient
from errors import AppError

@dataclass
class Supplier:
    id: str
    name: str
    phone: str | None
    active: bool = True

_client = ApiClient()

def _to_supplier(d):
    return Supplier(id=d["id"], name=d["name"], phone=d.get("phone"), active=bool(d.get("active", True)))

def list_suppliers(query: str = ""):
    rows=[_to_supplier(x) for x in _client.get_entity("suppliers")]
    q=query.strip().lower()
    if q: rows=[s for s in rows if q in s.name.lower() or (s.phone and q in s.phone)]
    return sorted(rows,key=lambda s:s.name)

def add_supplier(*, name: str, phone: str | None):
    if not name.strip(): raise AppError("اسم المورد مطلوب.")
    return _to_supplier(_client.command(f"cmd-create-supplier-{uuid.uuid4().hex[:12]}","createSupplier",{"name":name.strip(),"phone":phone.strip() if phone and phone.strip() else None,"branch_ids":[_client.branch_id]}))

def update_supplier(supplier: Supplier):
    raise AppError("تعديل المورد Online غير متاح حتى الآن؛ استخدم وضع Offline لهذه العملية.")
