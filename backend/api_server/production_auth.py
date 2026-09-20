from __future__ import annotations

import firebase_admin
from firebase_admin import auth

def verify_request(request):
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    headers = getattr(request, "headers", None)
    raw = headers.get("authorization") if headers is not None else None
    if not raw or not raw.lower().startswith("bearer "):
        return None
    try:
        claims = auth.verify_id_token(raw.split(" ", 1)[1].strip(), check_revoked=True)
    except Exception:
        return None
    uid = claims.get("uid") or claims.get("sub")
    tenant_id = claims.get("tenant_id")
    if not uid or not tenant_id:
        return None
    return {
        "uid": str(uid),
        "tenant_id": str(tenant_id),
        "branch_ids": frozenset(str(x) for x in claims.get("branch_ids", ())),
        "permissions": frozenset(str(x) for x in claims.get("permissions", ())),
    }
