"""Local/dev HTTP entrypoint for the ERP command boundary.

This is closer to the "deployed API" the project status doc describes than
an earlier version of this file was, but still isn't it. What changed: the
engine is now DurableERPCommandEngine (backend/functions/services/
durable_engine.py) instead of the plain in-memory ERPCommandEngine, so data
now survives restarts of this process via a local SQLite file. What's still
missing before this is a real deployed API:

1. Not Turso/libSQL — this is one process's local SQLite file
   (backend/api_server/data/dev_erp.db, git-ignored), not a managed remote
   database, and there's no multi-server coordination.
2. Auth: dev_auth.py is a static token table, not real Firebase ID-token
   verification. It exists only so this server can be exercised locally.

What IS real: the command dispatch, validation, permission checks,
idempotency (same commandId replayed returns the original result instead of
double-applying, even across a restart now), the ledger/audit trail, and
now durability — all running the actual production reference engine
(backend/functions/services/erp_engine.py), unmodified.

Run:
    pip install -r backend/api_server/requirements.txt
    uvicorn backend.api_server.main:app --reload --port 8000

Try it:
    curl -X POST http://localhost:8000/command \\
      -H "Authorization: Bearer dev-owner-token" \\
      -H "Content-Type: application/json" \\
      -d '{"commandId": "test-1", "command": "createSale", "branchId": "LOCAL_BRANCH",
           "payload": {"items": [{"product_id": "demo-product-1", "quantity": 1, "unit_price": "100"}],
                       "payments": [{"wallet_id": "demo-wallet-cash", "amount": "100"}]}}'

Restart the server and repeat the same curl command with the same
commandId ("test-1") — it returns the identical original result rather than
creating a second sale, and the product/wallet/customer/sale data from
before the restart is all still there.
"""
from __future__ import annotations

import sys
import os
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dataclasses import asdict, is_dataclass
from decimal import Decimal
import json as _json
import urllib.error
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api_server.dev_auth import verify_dev_token
from backend.api_server.production_auth import verify_request as verify_production_token
from backend.api_server.dev_seed import seed_dev_data
from backend.functions.api.http import handle
from backend.functions.services.durable_engine import DurableERPCommandEngine
from backend.functions.repositories.generic import set_tenant_scope, reset_tenant_scope
from backend.functions.offline.protocol import SyncProtocol
from shared.contracts.errors import DomainError

if os.getenv("APP_ENV", "development").lower() == "production" and os.getenv("AUTH_PROVIDER", "dev").lower() == "dev":
    raise RuntimeError("Refusing to start production with development-token authentication")

app = FastAPI(
    title="Mobile Shop ERP API (dev)",
    version="0.2.0-dev",
    description="Local/dev entrypoint only — see module docstring in main.py.",
)

if os.getenv("TURSO_DATABASE_URL") and os.getenv("TURSO_AUTH_TOKEN"):
    # Vercel Functions have a read-only deployment filesystem. Durable production
    # state is stored in Turso/libSQL; the local path is only a constructor fallback.
    _DB_PATH = Path(tempfile.gettempdir()) / "mobile-shop" / "dev_erp.db"
else:
    _DB_PATH = Path(__file__).resolve().parent / "data" / "dev_erp.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

if os.getenv("APP_ENV", "development").lower() == "production":
    if os.getenv("AUTH_PROVIDER", "dev").lower() != "firebase":
        raise RuntimeError("Production requires AUTH_PROVIDER=firebase")
    if not os.getenv("TURSO_DATABASE_URL") or not os.getenv("TURSO_AUTH_TOKEN"):
        raise RuntimeError("Production requires TURSO_DATABASE_URL and TURSO_AUTH_TOKEN")

# A single in-process engine instance shared by every request. Persists to
# _DB_PATH (see durable_engine.py) — survives restarts of this process, but
# is still one local SQLite file, not a managed remote database.
engine = DurableERPCommandEngine(_DB_PATH)
if os.getenv("APP_ENV", "development").lower() != "production":
    seed_dev_data(engine)
sync_protocol = SyncProtocol(connection=engine._conn)

verify_token = verify_production_token if os.getenv("AUTH_PROVIDER", "dev").lower() == "firebase" else verify_dev_token

# ─── Email/password login (backs POST /auth/login below) ───────────────────
#
# Neither dev_auth.py nor production_auth.py handle a login *exchange* — they
# only verify a bearer token that some other process already issued. This
# fills that gap for both modes:
#
# - firebase mode: calls the Firebase Identity Toolkit REST API (the same
#   HTTP endpoint the Firebase client SDKs call under the hood) to verify
#   email/password and mint a real Firebase ID token, then runs that token
#   straight through verify_production_token — no separate trust path.
#   Requires FIREBASE_WEB_API_KEY (the public *Web API key* from the
#   Firebase project settings — not a service-account secret).
# - dev mode: a static email/password table mirroring dev_auth.py's static
#   token table. Local/dev sandbox only, never used in production (guarded
#   the same way dev_auth.py's tokens already are).


class _LoginError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


_DEV_LOGIN_USERS = {
    "owner@dev.local": {"password": "dev1234", "token": "dev-owner-token", "display_name": "مدير النظام"},
    "cashier@dev.local": {"password": "dev1234", "token": "dev-cashier-token", "display_name": "كاشير"},
}


class _BearerOnlyRequest:
    """Minimal stand-in so verify_production_token(request) can read a
    freshly-minted ID token the same way it reads any other request."""

    def __init__(self, id_token: str):
        self.headers = {"authorization": f"Bearer {id_token}"}


def _firebase_sign_in(email: str, password: str) -> str:
    api_key = os.getenv("FIREBASE_WEB_API_KEY")
    if not api_key:
        raise _LoginError("إعداد الخادم غير مكتمل (FIREBASE_WEB_API_KEY).")
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = _json.dumps({"email": email, "password": password, "returnSecureToken": True}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = _json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = _json.loads(exc.read().decode())
            reason = (body.get("error") or {}).get("message", "")
        except Exception:
            reason = ""
        if reason in {"EMAIL_NOT_FOUND", "INVALID_PASSWORD", "INVALID_LOGIN_CREDENTIALS"}:
            raise _LoginError("بيانات الدخول غير صحيحة.") from exc
        raise _LoginError("تعذّر الاتصال بخدمة تسجيل الدخول.") from exc
    except urllib.error.URLError as exc:
        raise _LoginError("تعذّر الاتصال بخدمة تسجيل الدخول.") from exc
    return data["idToken"]


def _login(email: str, password: str) -> dict:
    """Returns the {token, tenant_id, account_id, display_name} payload the
    Flutter client's AuthService.login expects, or raises _LoginError."""
    if os.getenv("AUTH_PROVIDER", "dev").lower() == "firebase":
        id_token = _firebase_sign_in(email, password)
        claims = verify_production_token(_BearerOnlyRequest(id_token))
        if not claims:
            # Signed in with Firebase but the ID token carries no usable
            # tenant_id/branch_ids/permissions custom claims yet — the
            # account exists but hasn't been provisioned into the ERP.
            raise _LoginError("الحساب غير مُهيأ بعد. تواصل مع مدير النظام.")
        return {
            "token": id_token,
            "tenant_id": claims["tenant_id"],
            "account_id": claims["uid"],
            "display_name": email,
        }
    user = _DEV_LOGIN_USERS.get(email)
    if not user or user["password"] != password:
        raise _LoginError("بيانات الدخول غير صحيحة.")
    claims = verify_dev_token(_BearerOnlyRequest(user["token"]))
    return {
        "token": user["token"],
        "tenant_id": claims["tenant_id"],
        "account_id": claims["uid"],
        "display_name": user["display_name"],
    }

_ERROR_STATUS = {
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "BRANCH_ACCESS_DENIED": 403,
    "NOT_FOUND": 404,
    "TENANT_REQUIRED": 401,
    "SYNC_BATCH_TOO_LARGE": 400,
}


def _status_for(code: str | None) -> int:
    return _ERROR_STATUS.get(code, 400)


def _json_safe(value):
    """Domain objects are frozen dataclasses with Decimal/datetime fields —
    turn them into plain JSON-safe structures for the HTTP response."""
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _json_safe(v) for k, v in asdict(value).items()}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if hasattr(value, "isoformat"):  # datetime/date
        return value.isoformat()
    return value


class _RequestAdapter:
    """Bridges FastAPI's Request to the shape backend/functions/api/http.py
    expects: `.get_json()` for the parsed body, `.headers` for auth_verifier
    to read the Authorization header from."""

    def __init__(self, body: dict, headers):
        self._body = body
        self.headers = headers

    def get_json(self, silent: bool = True):
        return self._body


@app.get("/")
def root():
    """Deployment landing endpoint; the Vercel project hosts the API, not a browser UI."""
    return {
        "service": "Mobile Shop ERP API",
        "status": "ok",
        "health": "/health",
        "api": ["/auth/login", "/branches", "/products", "/query/{entity}", "/command", "/sync/upload", "/sync/changes"],
        "clients": ["Flutter mobile/admin", "Python desktop POS"],
    }


@app.get("/health")
def health():
    return {"status": "ok", "mode": os.getenv("APP_ENV", "development").lower(), "persistence": "turso/libsql" if os.getenv("TURSO_DATABASE_URL") else "sqlite"}


@app.post("/auth/login")
async def login_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    email = str((body or {}).get("email") or "").strip()
    password = str((body or {}).get("password") or "")
    if not email or not password:
        return JSONResponse(
            {"ok": False, "error": {"code": "INVALID_INPUT", "message": "البريد الإلكتروني وكلمة المرور مطلوبان.", "details": {}}},
            status_code=400,
        )
    try:
        data = _login(email, password)
    except _LoginError as exc:
        return JSONResponse({"ok": False, "error": {"code": "UNAUTHORIZED", "message": exc.message, "details": {}}}, status_code=401)
    return JSONResponse({"ok": True, "data": data})


@app.get("/branches")
def branches_endpoint(request: Request):
    claims = verify_token(request)
    if not claims:
        return JSONResponse({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "التوثيق مطلوب.", "details": {}}}, status_code=401)
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        return JSONResponse({"ok": False, "error": {"code": "TENANT_REQUIRED", "message": "هوية المستأجر مطلوبة.", "details": {}}}, status_code=401)
    token = set_tenant_scope(str(tenant_id))
    try:
        allowed = set(claims.get("branch_ids", ()))
        rows = [_json_safe(b) for b in engine.branches.all() if b.id in allowed]
        return JSONResponse({"ok": True, "data": rows})
    finally:
        reset_tenant_scope(token)


@app.get("/products")
def list_products_endpoint(request: Request, branch_id: str = "LOCAL_BRANCH"):
    """Tenant/branch-scoped product read endpoint."""
    claims = verify_token(request)
    if not claims:
        return JSONResponse({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "التوثيق مطلوب.", "details": {}}}, status_code=401)
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        return JSONResponse({"ok": False, "error": {"code": "TENANT_REQUIRED", "message": "هوية المستأجر مطلوبة.", "details": {}}}, status_code=401)
    if branch_id not in claims.get("branch_ids", ()):
        return JSONResponse(
            {"ok": False, "error": {"code": "BRANCH_ACCESS_DENIED", "message": "لا توجد صلاحية وصول لهذا الفرع.", "details": {}}},
            status_code=403,
        )
    if "inventory.read" not in claims.get("permissions", ()):
        return JSONResponse(
            {"ok": False, "error": {"code": "FORBIDDEN", "message": "لا توجد صلاحية قراءة للمخزون.", "details": {"permission": "inventory.read"}}},
            status_code=403,
        )

    token = set_tenant_scope(str(tenant_id))
    try:
        products = []
        for p in engine.products.all():
            payload = _json_safe(p)
            payload["quantity"] = str(engine._available_qty(branch_id, p.id))
            products.append(payload)
        return JSONResponse({"ok": True, "data": products})
    finally:
        reset_tenant_scope(token)



_QUERY_REPOS = {
    "products": "products", "customers": "customers", "suppliers": "suppliers",
    "sales": "sales", "purchases": "purchases", "expenses": "expenses",
    "maintenance": "maintenance", "installments": "installments", "wallets": "wallets",
    "ledger": "ledger", "audit": "audit", "employees": "employees", "installment-payments": "installment_payments", "maintenance-parts": "maintenance_parts", "branches": "branches", "users": "users", "roles": "roles",
}

@app.get("/sales")
def list_sales_endpoint(request: Request, branch_id: str = "LOCAL_BRANCH", limit: int = 50):
    """Dedicated tenant/branch-scoped sales read endpoint for the desktop Online mode."""
    claims = verify_token(request)
    if not claims:
        return JSONResponse({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "التوثيق مطلوب.", "details": {}}}, status_code=401)
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        return JSONResponse({"ok": False, "error": {"code": "TENANT_REQUIRED", "message": "هوية المستأجر مطلوبة.", "details": {}}}, status_code=401)
    if branch_id not in claims.get("branch_ids", ()):
        return JSONResponse({"ok": False, "error": {"code": "BRANCH_ACCESS_DENIED", "message": "لا توجد صلاحية وصول لهذا الفرع.", "details": {}}}, status_code=403)
    if "sales.read" not in claims.get("permissions", ()):
        return JSONResponse({"ok": False, "error": {"code": "FORBIDDEN", "message": "لا توجد صلاحية قراءة للمبيعات.", "details": {"permission": "sales.read"}}}, status_code=403)
    if limit < 1 or limit > 500:
        return JSONResponse({"ok": False, "error": {"code": "INVALID_INPUT", "message": "limit يجب أن يكون بين 1 و500.", "details": {}}}, status_code=400)

    token = set_tenant_scope(str(tenant_id))
    try:
        rows = []
        for value in engine.sales.all():
            row = _json_safe(value)
            if isinstance(row, dict) and row.get("branch_id") != branch_id:
                continue
            rows.append(row)
            if len(rows) >= limit:
                break
        return JSONResponse({"ok": True, "data": rows})
    finally:
        reset_tenant_scope(token)


@app.get("/reports")
def reports_endpoint(request: Request, branch_id: str = "LOCAL_BRANCH", start: str | None = None, end: str | None = None):
    claims = verify_token(request)
    if not claims:
        return JSONResponse({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "التوثيق مطلوب.", "details": {}}}, status_code=401)
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        return JSONResponse({"ok": False, "error": {"code": "TENANT_REQUIRED", "message": "هوية المستأجر مطلوبة.", "details": {}}}, status_code=401)
    if branch_id not in claims.get("branch_ids", ()):
        return JSONResponse({"ok": False, "error": {"code": "BRANCH_ACCESS_DENIED", "message": "لا توجد صلاحية وصول لهذا الفرع.", "details": {}}}, status_code=403)
    if "reports.read" not in claims.get("permissions", ()):
        return JSONResponse({"ok": False, "error": {"code": "FORBIDDEN", "message": "لا توجد صلاحية لقراءة التقارير.", "details": {"permission": "reports.read"}}}, status_code=403)
    try:
        from datetime import date
        start_date = date.fromisoformat(start) if start else None
        end_date = date.fromisoformat(end) if end else None
    except ValueError:
        return JSONResponse({"ok": False, "error": {"code": "INVALID_INPUT", "message": "صيغة التاريخ يجب أن تكون YYYY-MM-DD.", "details": {}}}, status_code=400)
    token = set_tenant_scope(str(tenant_id))
    try:
        return JSONResponse({"ok": True, "data": _json_safe(engine.reports_full(branch_id, start_date, end_date))})
    finally:
        reset_tenant_scope(token)


@app.get("/query/{entity}")
def query_endpoint(request: Request, entity: str, branch_id: str = "LOCAL_BRANCH",
                   limit: int = 100):
    """Tenant/branch-scoped read API for operational clients."""
    claims = verify_token(request)
    if not claims:
        return JSONResponse({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "التوثيق مطلوب.", "details": {}}}, status_code=401)
    if entity not in _QUERY_REPOS or branch_id not in claims.get("branch_ids", ()):
        return JSONResponse({"ok": False, "error": {"code": "BRANCH_ACCESS_DENIED", "message": "لا توجد صلاحية وصول.", "details": {}}}, status_code=403)
    if limit < 1 or limit > 500:
        return JSONResponse({"ok": False, "error": {"code": "INVALID_INPUT", "message": "limit يجب أن يكون بين 1 و500.", "details": {}}}, status_code=400)
    tenant_id = claims.get("tenant_id")
    if not tenant_id:
        return JSONResponse({"ok": False, "error": {"code": "TENANT_REQUIRED", "message": "هوية المستأجر مطلوبة.", "details": {}}}, status_code=401)
    permission_by_entity = {
        "products": "inventory.read", "customers": "customers.read",
        "suppliers": "suppliers.read", "sales": "sales.read",
        "purchases": "purchases.read", "expenses": "expenses.read",
        "maintenance": "maintenance.read", "installments": "installments.read",
        "wallets": "wallets.read", "ledger": "accounting.read",
        "audit": "audit.read", "employees": "employees.read", "installment-payments": "installments.read", "maintenance-parts": "maintenance.read", "branches": "branches.read", "users": "users.read", "roles": "roles.read",
    }
    required_permission = permission_by_entity[entity]
    if required_permission not in claims.get("permissions", ()):
        return JSONResponse({"ok": False, "error": {"code": "FORBIDDEN", "message": "لا توجد صلاحية قراءة لهذا المورد.", "details": {"permission": required_permission}}}, status_code=403)
    token = set_tenant_scope(str(tenant_id))
    try:
        repo = getattr(engine, _QUERY_REPOS[entity])
        rows = []
        for value in repo.all():
            row = _json_safe(value)
            # Branch-owned entities are filtered server-side. Global catalog records
            # (products/customers/suppliers) remain tenant-scoped and are not
            # exposed across tenants.
            if isinstance(row, dict):
                if "branch_id" in row and row["branch_id"] != branch_id:
                    continue
                if entity in {"suppliers", "employees"} and branch_id not in row.get("branch_ids", ()):
                    continue
            rows.append(row)
            if len(rows) >= limit:
                break
        return JSONResponse({"ok": True, "data": rows})
    finally:
        reset_tenant_scope(token)


@app.post("/sync/upload")
async def sync_upload_endpoint(request: Request):
    claims = verify_token(request)
    if not claims:
        return JSONResponse({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "التوثيق مطلوب.", "details": {}}}, status_code=401)
    body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get("commands"), list):
        return JSONResponse({"ok": False, "error": {"code": "INVALID_INPUT", "message": "commands يجب أن تكون قائمة.", "details": {}}}, status_code=400)
    tenant_id = claims.get("tenant_id")
    branch_id = body.get("branch_id")
    if not tenant_id or branch_id not in claims.get("branch_ids", ()):
        return JSONResponse({"ok": False, "error": {"code": "BRANCH_ACCESS_DENIED", "message": "لا توجد صلاحية وصول للفرع.", "details": {}}}, status_code=403)

    def execute(envelope):
        from shared.contracts.commands import CommandContext
        from backend.functions.api.dispatch import dispatch
        ctx = CommandContext(
            envelope["command_id"], claims["uid"], branch_id,
            frozenset(claims.get("permissions", ())), tenant_id,
        )
        command_name = envelope.get("command")
        payload = envelope.get("payload", {})
        return dispatch(engine, command_name, ctx, **payload)

    try:
        result = sync_protocol.upload(body["commands"], tenant_id=tenant_id, branch_id=branch_id, executor=execute)
        return JSONResponse({"ok": True, "data": result})
    except DomainError as exc:
        error = exc.as_dict()
        return JSONResponse({"ok": False, "error": error}, status_code=_status_for(error.get("code")))


@app.get("/sync/changes")
def sync_changes(request: Request, branch_id: str, cursor: int = 0, limit: int = 100):
    claims = verify_token(request)
    if not claims:
        return JSONResponse({"ok": False, "error": {"code": "UNAUTHORIZED", "message": "التوثيق مطلوب.", "details": {}}}, status_code=401)
    tenant_id = claims.get("tenant_id")
    if not tenant_id or branch_id not in claims.get("branch_ids", ()):
        return JSONResponse({"ok": False, "error": {"code": "BRANCH_ACCESS_DENIED", "message": "لا توجد صلاحية وصول للفرع.", "details": {}}}, status_code=403)
    try:
        return JSONResponse({"ok": True, "data": sync_protocol.download(tenant_id=tenant_id, branch_id=branch_id, cursor=cursor, limit=limit)})
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}}, status_code=400)

@app.post("/command")
async def command_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    adapter = _RequestAdapter(body if isinstance(body, dict) else {}, request.headers)

    # http.handle() raises DomainError directly for auth/branch-access
    # failures but returns {'ok': False, ...} for dispatch-level errors —
    # that split is existing, tested behavior (see
    # tests/integration/test_security_hardening.py); this endpoint handles
    # both shapes rather than changing it.
    try:
        result = handle(adapter, engine, verify_token)
    except DomainError as exc:
        error = exc.as_dict()
        return JSONResponse({"ok": False, "error": error}, status_code=_status_for(error.get("code")))

    if not result.get("ok"):
        error = result.get("error", {})
        return JSONResponse(result, status_code=_status_for(error.get("code")))
    return JSONResponse({"ok": True, "data": _json_safe(result["data"])})
