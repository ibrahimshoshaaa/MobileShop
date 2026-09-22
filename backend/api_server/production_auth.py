from __future__ import annotations

import json
import os

import firebase_admin
from firebase_admin import auth, credentials


def _initialize_firebase() -> None:
    if firebase_admin._apps:
        return

    raw_credentials = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if raw_credentials:
        try:
            service_account = json.loads(raw_credentials)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON must contain valid JSON") from exc
        firebase_admin.initialize_app(credentials.Certificate(service_account))
        return

    # Falls back to Google Application Default Credentials when the runtime
    # provides them (useful outside Vercel).
    firebase_admin.initialize_app()


def verify_request(request):
    _initialize_firebase()
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
