from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

import inventory_repo
from errors import AppError
from local_store import DEFAULT_BRANCH_ID, DEFAULT_TENANT_ID, get_store

ENTITY = "sale"

PAYMENT_METHODS = [
    ("CASH", "نقدي"),
    ("WALLET", "محفظة"),
    ("CARD", "بطاقة"),
    ("CREDIT", "آجل"),
]
PAYMENT_METHOD_LABELS = dict(PAYMENT_METHODS)


@dataclass
class SaleItem:
    product_id: str
    product_name: str
    quantity: int
    unit_price: float

    @property
    def line_total(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Payment:
    method: str
    amount: float


@dataclass
class Sale:
    id: str
    customer_id: str | None
    customer_name: str | None
    items: list[SaleItem]
    subtotal: float
    discount: float
    total: float
    payments: list[Payment]
    status: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _item_to_payload(i: SaleItem) -> dict:
    return {"product_id": i.product_id, "product_name": i.product_name, "quantity": i.quantity, "unit_price": i.unit_price}


def _item_from_payload(m: dict) -> SaleItem:
    return SaleItem(product_id=m["product_id"], product_name=m["product_name"], quantity=int(m["quantity"]), unit_price=float(m["unit_price"]))


def _payment_to_payload(p: Payment) -> dict:
    return {"method": p.method, "amount": p.amount}


def _payment_from_payload(m: dict) -> Payment:
    return Payment(method=m["method"], amount=float(m["amount"]))


def _to_payload(s: Sale) -> dict:
    return {
        "id": s.id,
        "customer_id": s.customer_id,
        "customer_name": s.customer_name,
        "items": [_item_to_payload(i) for i in s.items],
        "subtotal": s.subtotal,
        "discount": s.discount,
        "total": s.total,
        "payments": [_payment_to_payload(p) for p in s.payments],
        "status": s.status,
        "created_at": s.created_at.isoformat(),
    }


def _to_sale(payload: dict) -> Sale:
    return Sale(
        id=payload["id"],
        customer_id=payload.get("customer_id"),
        customer_name=payload.get("customer_name"),
        items=[_item_from_payload(i) for i in payload["items"]],
        subtotal=float(payload["subtotal"]),
        discount=float(payload["discount"]),
        total=float(payload["total"]),
        payments=[_payment_from_payload(p) for p in payload["payments"]],
        status=payload["status"],
        created_at=datetime.fromisoformat(payload["created_at"]),
    )


def _new_id(prefix: str = "sale") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def list_recent_sales(limit: int = 50) -> list[Sale]:
    store = get_store()
    rows = store.list_records(tenant_id=DEFAULT_TENANT_ID, entity=ENTITY)
    sales = sorted((_to_sale(r["payload"]) for r in rows), key=lambda s: s.created_at, reverse=True)
    return sales[:limit]


def create_sale(*, items: list[SaleItem], payments: list[Payment], customer_id: str | None = None,
                 customer_name: str | None = None, discount: float = 0) -> Sale:
    if not items:
        raise AppError("الفاتورة بدون أصناف.")
    if discount < 0:
        raise AppError("الخصم لا يمكن أن يكون سالبًا.")

    subtotal = sum(i.line_total for i in items)
    total = subtotal - discount
    if total < 0:
        raise AppError("الخصم أكبر من إجمالي الفاتورة.")

    paid = sum(p.amount for p in payments)
    if abs(paid - total) > 0.01:
        raise AppError(f"إجمالي المدفوعات ({paid:.2f}) لا يساوي إجمالي الفاتورة ({total:.2f}).")

    # Validate stock for every line before touching anything (see the same
    # note in the Dart SqliteSalesRepository about this not yet being one
    # atomic transaction end-to-end).
    current_products = {p.id: p for p in inventory_repo.list_products()}
    for item in items:
        product = current_products.get(item.product_id)
        if product is None:
            raise AppError(f'الصنف "{item.product_name}" لم يعد موجودًا.')
        if product.product_type != "SERVICE" and product.quantity < item.quantity:
            raise AppError(f'الكمية غير كافية لـ "{product.name}" — المتاح: {product.quantity}.')

    sale_id = _new_id()
    for item in items:
        inventory_repo.adjust_stock(item.product_id, -item.quantity, f"بيع فاتورة #{sale_id}")

    sale = Sale(
        id=sale_id, customer_id=customer_id, customer_name=customer_name, items=items,
        subtotal=subtotal, discount=discount, total=total, payments=payments, status="COMPLETED",
    )
    store = get_store()
    store.upsert_record(
        entity=ENTITY, record_id=sale.id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(sale), expected_version=0,
    )
    store.submit_command(
        command_id=_new_id("cmd-sale"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="createSale",
        payload={
            "customer_id": customer_id,
            "customer_name": customer_name,
            "items": [_item_to_payload(i) for i in items],
            "payments": [_payment_to_payload(p) for p in payments],
            "discount": discount,
        },
    )
    return sale


def void_sale(sale_id: str) -> Sale:
    store = get_store()
    current = store.get_record(entity=ENTITY, record_id=sale_id, tenant_id=DEFAULT_TENANT_ID)
    if current is None:
        raise AppError("الفاتورة غير موجودة.")
    sale = _to_sale(current["payload"])
    if sale.status == "VOIDED":
        raise AppError("الفاتورة ملغاة بالفعل.")

    for item in sale.items:
        try:
            inventory_repo.adjust_stock(item.product_id, item.quantity, f"إلغاء فاتورة #{sale_id}")
        except AppError:
            # Product may have been deleted since the sale — voiding still
            # proceeds so the invoice itself is correctly marked.
            pass

    voided = replace(sale, status="VOIDED")
    store.upsert_record(
        entity=ENTITY, record_id=sale_id, tenant_id=DEFAULT_TENANT_ID,
        branch_id=DEFAULT_BRANCH_ID, payload=_to_payload(voided), expected_version=current["version"],
    )
    store.submit_command(
        command_id=_new_id("cmd-void"), tenant_id=DEFAULT_TENANT_ID, branch_id=DEFAULT_BRANCH_ID,
        command="voidSale", payload={"sale_id": sale_id},
    )
    return voided
