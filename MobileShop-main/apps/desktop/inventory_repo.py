"""Desktop-side inventory repository.

Deliberately mirrors apps/admin_mobile/lib/features/inventory/*.dart: same
payload keys (so records are conceptually interchangeable with the mobile
app's, even though each device has its own local SQLite file and there's no
sync between them yet), same validation rules, same simplification of
carrying `quantity` directly on the product record instead of deriving it
from StockMovement rows the way shared/models/erp.py's Product does.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, replace

from errors import AppError
from local_store import DEFAULT_BRANCH_ID, DEFAULT_TENANT_ID, get_store

ENTITY = "product"

PRODUCT_TYPES = [
    ("PHONE_NEW", "الهواتف الجديدة"),
    ("PHONE_USED", "الهواتف المستعملة"),
    ("ACCESSORY", "الإكسسوارات"),
    ("SPARE_PART", "قطع الغيار"),
    ("SERVICE", "الخدمات"),
]
PRODUCT_TYPE_LABELS = dict(PRODUCT_TYPES)
PRODUCT_TYPE_CODES = [code for code, _ in PRODUCT_TYPES]


@dataclass
class Product:
    id: str
    name: str
    sku: str
    product_type: str
    barcode: str | None
    selling_price: float
    default_cost: float
    reorder_level: int
    quantity: int
    active: bool = True

    @property
    def type_label(self) -> str:
        return PRODUCT_TYPE_LABELS.get(self.product_type, self.product_type)

    @property
    def is_low_stock(self) -> bool:
        return self.product_type != "SERVICE" and self.quantity <= self.reorder_level


def _to_product(payload: dict) -> Product:
    return Product(
        id=payload["id"],
        name=payload["name"],
        sku=payload["sku"],
        product_type=payload["product_type"],
        barcode=payload.get("barcode"),
        selling_price=float(payload["selling_price"]),
        default_cost=float(payload["default_cost"]),
        reorder_level=int(payload["reorder_level"]),
        quantity=int(payload["quantity"]),
        active=bool(payload.get("active", True)),
    )


def _to_payload(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "product_type": p.product_type,
        "barcode": p.barcode,
        "selling_price": p.selling_price,
        "default_cost": p.default_cost,
        "reorder_level": p.reorder_level,
        "quantity": p.quantity,
        "active": p.active,
    }


def _new_id(prefix: str = "p") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _seed_if_empty() -> None:
    store = get_store()
    existing = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=ENTITY)
    if existing:
        return
    seed = [
        Product("p1", "iPhone 13 128GB", "PH-IP13-128", "PHONE_NEW", "6901234567001", 28000, 24500, 3, 5),
        Product("p2", "سامسونج A54 مستعمل", "PH-SA54-USED", "PHONE_USED", "6901234567002", 9500, 7800, 2, 1),
        Product("p3", "شاحن سريع 20 وات", "ACC-CHG-20W", "ACCESSORY", "6901234567003", 350, 180, 10, 4),
        Product("p4", "شاشة آيفون 12", "SP-SCR-IP12", "SPARE_PART", None, 1200, 700, 3, 6),
        Product("p5", "صيانة عامة", "SVC-GEN", "SERVICE", None, 150, 0, 0, 0),
    ]
    for p in seed:
        store.upsert_record(
            entity=ENTITY, record_id=p.id, tenant_id=DEFAULT_TENANT_ID,
            branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(p), expected_version=0,
        )


def list_products(product_type: str | None = None, query: str = "") -> list[Product]:
    _seed_if_empty()
    store = get_store()
    rows = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=ENTITY)
    products = [_to_product(r["payload"]) for r in rows]
    q = query.strip().lower()
    result = []
    for p in products:
        if product_type is not None and p.product_type != product_type:
            continue
        if q and q not in p.name.lower() and q not in p.sku.lower() and not (p.barcode and q in p.barcode.lower()):
            continue
        result.append(p)
    return sorted(result, key=lambda p: p.name)


def add_product(*, name: str, sku: str, product_type: str, barcode: str | None,
                 selling_price: float, default_cost: float, reorder_level: int,
                 opening_quantity: int) -> Product:
    if not name.strip():
        raise AppError("اسم الصنف مطلوب.")
    if not sku.strip():
        raise AppError("رمز الصنف (SKU) مطلوب.")
    existing = list_products()
    if any(p.sku.lower() == sku.strip().lower() for p in existing):
        raise AppError(f'رمز الصنف (SKU) "{sku}" مستخدم بالفعل.')
    clean_barcode = barcode.strip() if barcode and barcode.strip() else None
    if clean_barcode and any(p.barcode == clean_barcode for p in existing):
        raise AppError("الباركود مستخدم بالفعل لصنف آخر.")
    product = Product(
        id=_new_id(), name=name.strip(), sku=sku.strip(), product_type=product_type,
        barcode=clean_barcode, selling_price=selling_price, default_cost=default_cost,
        reorder_level=reorder_level, quantity=opening_quantity,
    )
    store = get_store()
    store.upsert_record(
        entity=ENTITY, record_id=product.id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(product), expected_version=0,
    )
    store.submit_command(
        command_id=_new_id("cmd-create"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="createProduct", payload=_to_payload(product),
    )
    return product


def update_product(product: Product) -> Product:
    store = get_store()
    current = store.get_record(entity=ENTITY, record_id=product.id, tenant_id=DEFAULT_TENANT_ID)
    if current is None:
        raise AppError("الصنف غير موجود.")
    others = [p for p in list_products() if p.id != product.id]
    if any(p.sku.lower() == product.sku.lower() for p in others):
        raise AppError("رمز الصنف (SKU) مستخدم بالفعل لصنف آخر.")
    try:
        store.upsert_record(
            entity=ENTITY, record_id=product.id, tenant_id=DEFAULT_TENANT_ID,
            branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(product), expected_version=current["version"],
        )
    except ValueError as e:
        if str(e) == "STALE_VERSION":
            raise AppError('تعذّر الحفظ: تم تعديل هذا الصنف من جهاز آخر في نفس الوقت. أعد الفتح وحاول مجددًا.') from e
        raise
    store.submit_command(
        command_id=_new_id("cmd-update"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="updateProduct", payload=_to_payload(product),
    )
    return product


def adjust_stock(product_id: str, delta: int, reason: str) -> Product:
    if not reason.strip():
        raise AppError("يجب إدخال سبب حركة المخزون.")
    store = get_store()
    current = store.get_record(entity=ENTITY, record_id=product_id, tenant_id=DEFAULT_TENANT_ID)
    if current is None:
        raise AppError("الصنف غير موجود.")
    product = _to_product(current["payload"])
    new_quantity = product.quantity + delta
    if new_quantity < 0:
        raise AppError("الكمية الناتجة سالبة — تحقق من الرصيد الحالي.")
    updated = replace(product, quantity=new_quantity)
    try:
        store.upsert_record(
            entity=ENTITY, record_id=product_id, tenant_id=DEFAULT_TENANT_ID,
            branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(updated), expected_version=current["version"],
        )
    except ValueError as e:
        if str(e) == "STALE_VERSION":
            raise AppError("تعذّر تحديث الرصيد: تم تعديل الصنف من جهاز آخر في نفس الوقت.") from e
        raise
    store.submit_command(
        command_id=_new_id("cmd-stock"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="adjustStock", payload={"product_id": product_id, "delta": delta, "reason": reason},
    )
    return updated
