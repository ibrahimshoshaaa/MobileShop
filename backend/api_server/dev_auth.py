"""DEV-ONLY auth verifier for the local API server.

This is a static, in-memory token table — it exists purely so the command
boundary in backend/functions/api/http.py can be exercised locally without a
real identity provider wired up. It MUST be replaced with real Firebase
ID-token verification (or another real identity provider) before this is
anything but a local dev sandbox. See backend/api_server/README.md for what
"real" auth needs to look like here.
"""
from __future__ import annotations

# token -> claims. Anyone holding one of these literal strings gets full
# access to the matching branch — obviously unacceptable outside a local dev
# sandbox. Never reuse this pattern past local development.
_DEV_TOKENS = {
    "dev-owner-token": {
        "uid": "dev-owner",
        "tenant_id": "dev-tenant",
        "branch_ids": ("LOCAL_BRANCH",),
        "permissions": (
            "sales.create", "sales.read", "sales.void", "sales.return", "sales.discount",
            "inventory.read", "customers.read", "wallets.read", "products.edit", "customers.edit", "customers.collect", "suppliers.edit", "wallets.edit",
            "purchases.create", "purchases.pay_supplier", "expenses.create",
            "stock.adjust", "stock.transfer", "wallet.adjust", "wallet.transfer",
            "transfer.create", "transfer.override_commission",
            "installments.create", "installments.collect",
            "maintenance.create", "maintenance.update", "maintenance.parts",
            "closing.close", "permissions.change", "settings.change",
            "employees.salary", "inventory.create_unit",
        ),
    },
    "dev-cashier-token": {
        "uid": "dev-cashier",
        "tenant_id": "dev-tenant",
        "branch_ids": ("LOCAL_BRANCH",),
        "permissions": ("sales.create", "sales.read", "inventory.read", "customers.read", "wallets.read", "customers.edit", "installments.collect"),
    },
}


def verify_dev_token(request) -> dict | None:
    """Reads `Authorization: Bearer <token>` off `request.headers` and looks
    it up in the static table above. Returns None (=> UNAUTHORIZED) for
    anything else — no token, unknown token, wrong header shape."""
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    auth_header = headers.get("authorization") or headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    claims = _DEV_TOKENS.get(token)
    if not claims:
        return None
    return {
        "uid": claims["uid"],
        "branch_ids": frozenset(claims["branch_ids"]),
        "permissions": frozenset(claims["permissions"]),
        "tenant_id": claims["tenant_id"],
    }
