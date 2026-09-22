from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime

from api_client import ApiClient, ApiError
from errors import AppError


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
    created_at: datetime


_client = ApiClient()


def _new_id(prefix: str = "cmd-sale") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _to_sale(payload: dict, wallets_by_id: dict[str, dict] | None = None) -> Sale:
    wallets_by_id = wallets_by_id or {}
    items = [
        SaleItem(
            product_id=i["product_id"],
            product_name=i.get("product_name") or i["product_id"],
            quantity=int(float(i["quantity"])),
            unit_price=float(i["unit_price"]),
        )
        for i in payload.get("items", [])
    ]
    payments = []
    for p in payload.get("payments", []):
        wallet = wallets_by_id.get(p.get("wallet_id"), {})
        method = wallet.get("wallet_type", "CASH")
        payments.append(Payment(method=method, amount=float(p["amount"])))
    created_at = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
    return Sale(
        id=payload["id"],
        customer_id=payload.get("customer_id"),
        customer_name=payload.get("customer_name"),
        items=items,
        subtotal=float(payload["subtotal"]),
        discount=float(payload.get("discount", 0)),
        total=float(payload["total"]),
        payments=payments,
        status=payload.get("status", "COMPLETED"),
        created_at=created_at,
    )


def list_recent_sales(limit: int = 50) -> list[Sale]:
    raw = _client.get_sales(limit)
    wallets = {w["id"]: w for w in _client.get_wallets()}
    return [_to_sale(row, wallets) for row in raw]


def _wallet_for_method(method: str) -> str | None:
    if method == "CREDIT":
        return None
    wanted = {"CASH": "CASH", "WALLET": "WALLET", "CARD": "CARD"}.get(method)
    if wanted is None:
        raise AppError("طريقة الدفع غير مدعومة.")
    wallets = _client.get_wallets()
    wallet = next((w for w in wallets if w.get("active", True) and w.get("wallet_type") == wanted), None)
    if wallet is None:
        raise AppError(f"لا توجد محفظة مفعّلة من نوع {PAYMENT_METHOD_LABELS[method]} على السيرفر.")
    return wallet["id"]


def create_sale(*, items: list[SaleItem], payments: list[Payment],
                customer_id: str | None = None, customer_name: str | None = None,
                discount: float = 0) -> Sale:
    if not items:
        raise AppError("الفاتورة بدون أصناف.")
    if discount < 0:
        raise AppError("الخصم لا يمكن أن يكون سالبًا.")

    subtotal = sum(i.line_total for i in items)
    total = subtotal - discount
    if total < 0:
        raise AppError("الخصم أكبر من إجمالي الفاتورة.")

    paid = sum(p.amount for p in payments)
    if abs(paid - total) > 0.01 and not (customer_id and paid <= total):
        raise AppError(f"إجمالي المدفوعات ({paid:.2f}) لا يساوي إجمالي الفاتورة ({total:.2f}).")

    api_payments = []
    for payment in payments:
        wallet_id = _wallet_for_method(payment.method)
        if wallet_id is None:
            raise AppError("البيع الآجل لا يحتاج دفعة. اترك الدفعات فارغة.")
        api_payments.append({"wallet_id": wallet_id, "amount": payment.amount})

    data = _client.command(_new_id(), "createSale", {
        "customer_id": customer_id,
        "items": [
            {
                "product_id": i.product_id,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
            }
            for i in items
        ],
        "payments": api_payments,
        "discount": discount,
    })
    wallets = {w["id"]: w for w in _client.get_wallets()}
    return _to_sale(data, wallets)


def void_sale(sale_id: str) -> Sale:
    data = _client.command(_new_id("cmd-void"), "voidSale", {"sale_id": sale_id})
    wallets = {w["id"]: w for w in _client.get_wallets()}
    return _to_sale(data, wallets)
