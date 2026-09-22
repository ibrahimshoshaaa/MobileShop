"""Online-mode inventory repository.

Same public functions as inventory_repo.py (list_products / add_product /
update_product / adjust_stock) so inventory_tab.py can use either module
interchangeably (see app.py's MOBILE_SHOP_ERP_MODE switch) — but this one
calls the real backend/api_server over HTTP instead of the local SQLite
file, using the actual production ERPCommandEngine on the other end.

What's different from offline mode, worth knowing:
- The backend Product has no `quantity` field of its own — it's derived
  from StockMovement rows per branch. GET /products (added alongside this)
  computes it server-side via engine._available_qty, so the shape looks the
  same to this module's caller, but the number reflects the *server's*
  stock ledger, not a local counter.
- update_product requires the API's `updateProduct` command, which needs
  fields wrapped as `changes` (see backend/functions/api/dispatch.py) — this
  module handles that, the caller doesn't need to know.
- Every write here reaches the server immediately; there is no local outbox
  and no offline queueing in this mode. If the server is unreachable, the
  call fails with an ApiError right away instead of queueing for later —
  true offline-first behavior in online mode would need its own design
  (retry queue, conflict handling), which this does not attempt.
"""
from __future__ import annotations

import uuid

from api_client import ApiClient, ApiError
from errors import AppError
from inventory_repo import PRODUCT_TYPE_CODES, PRODUCT_TYPE_LABELS, PRODUCT_TYPES, Product  # re-exported for the tab

__all__ = ["PRODUCT_TYPES", "PRODUCT_TYPE_LABELS", "PRODUCT_TYPE_CODES", "Product", "list_products", "add_product", "update_product", "adjust_stock"]

_client = ApiClient()


def _to_product(d: dict) -> Product:
    return Product(
        id=d["id"], name=d["name"], sku=d["sku"], product_type=d["product_type"],
        barcode=d.get("barcode"), selling_price=float(d["selling_price"]), default_cost=float(d["default_cost"]),
        reorder_level=int(float(d.get("reorder_level", 0))), quantity=int(float(d.get("quantity", 0))),
        active=bool(d.get("active", True)),
    )


def _new_id(prefix: str = "cmd") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def list_products(product_type: str | None = None, query: str = "") -> list[Product]:
    raw = _client.get_products()
    products = [_to_product(d) for d in raw]
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
    data = _client.command(_new_id("cmd-create"), "createProduct", {
        "product": {
            "name": name, "sku": sku, "product_type": product_type, "barcode": barcode or None,
            "selling_price": selling_price, "default_cost": default_cost, "reorder_level": reorder_level,
        },
    })
    product = _to_product({**data, "quantity": 0})
    if opening_quantity:
        adjust_stock(product.id, opening_quantity, "رصيد افتتاحي")
        product = next((p for p in list_products() if p.id == product.id), product)
    return product


def update_product(product: Product) -> Product:
    _client.command(_new_id("cmd-update"), "updateProduct", {
        "product_id": product.id,
        "changes": {
            "name": product.name, "sku": product.sku, "product_type": product.product_type,
            "barcode": product.barcode, "selling_price": product.selling_price,
            "default_cost": product.default_cost, "reorder_level": product.reorder_level,
            "active": product.active,
        },
    })
    return product


def adjust_stock(product_id: str, delta: int, reason: str) -> Product:
    if not reason.strip():
        raise AppError("يجب إدخال سبب حركة المخزون.")
    _client.command(_new_id("cmd-stock"), "adjustStock", {"product_id": product_id, "quantity": delta, "reason": reason})
    updated = next((p for p in list_products() if p.id == product_id), None)
    if updated is None:
        raise ApiError("تعذّر العثور على الصنف بعد تحديث الرصيد.")
    return updated
