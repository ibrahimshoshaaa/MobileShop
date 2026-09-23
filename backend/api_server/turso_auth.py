"""Turso-backed auth: replaces Firebase entirely.

Users (email, password hash, tenant_id, branch_ids, permissions) live in a
plain `auth_users` table in the same Turso/libSQL database the ERP engine
already uses (see backend/functions/services/durable_engine.py — same
connection pattern, same TURSO_DATABASE_URL/TURSO_AUTH_TOKEN env vars).
Falls back to a local SQLite file when those aren't set, so this also works
for local dev with AUTH_PROVIDER=turso.

Passwords: PBKDF2-HMAC-SHA256, 200k iterations, random 16-byte salt per
user. Stdlib only (hashlib/hmac) — no bcrypt/passlib dependency needed.

Tokens: a small hand-rolled HS256 JWT (header.payload.signature, all
base64url, HMAC-SHA256 signature) signed with AUTH_JWT_SECRET. Same shape
as a real JWT, just implemented directly with hmac/json/base64 instead of
pulling in PyJWT for something this small. Verification always checks the
signature (constant-time compare) and expiry before trusting any claim.

Public surface:
    sign_in(email, password) -> {token, tenant_id, account_id, display_name}
    verify_request(request)  -> {uid, tenant_id, branch_ids, permissions} | None
    create_user(...)         -> provisioning helper (also exposed as a CLI
                                 below: `python -m backend.api_server.turso_auth
                                 create-user ...`)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

_PBKDF2_ITERATIONS = 200_000
_TOKEN_TTL_SECONDS = 12 * 60 * 60  # 12h; client re-logs in after this

# Every permission string referenced anywhere in backend/functions and
# backend/api_server. Lets `create-user --permissions all` grant a full
# owner account without hand-typing every string.
ALL_PERMISSIONS = [
    "accounting.read", "audit.read", "branches.manage", "branches.read",
    "closing.close", "customers.collect", "customers.edit", "customers.read",
    "employees.read", "employees.salary", "expenses.create", "expenses.read",
    "installments.collect", "installments.create", "installments.read",
    "inventory.create_unit", "inventory.read", "maintenance.create",
    "maintenance.parts", "maintenance.read", "maintenance.update",
    "permissions.change", "products.edit", "purchases.create",
    "purchases.pay_supplier", "purchases.read", "reports.read",
    "roles.manage", "roles.read", "sales.create", "sales.discount",
    "sales.read", "sales.return", "sales.void", "settings.change",
    "stock.adjust", "stock.transfer", "suppliers.edit", "suppliers.read",
    "transfer.create", "transfer.override_commission", "users.manage",
    "users.read", "wallet.adjust", "wallet.transfer", "wallets.edit",
    "wallets.read",
]


class AuthError(Exception):
    """Raised for any user-facing sign-in failure (wrong password, no such
    user, disabled account). main.py maps this straight to the same
    UNAUTHORIZED response it used for the old Firebase _LoginError."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# ─── password hashing ───────────────────────────────────────────────────

def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_hex, hash_hex = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


# ─── tokens (hand-rolled HS256 JWT) ─────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _secret() -> bytes:
    raw = os.getenv("AUTH_JWT_SECRET")
    if not raw:
        raise RuntimeError("AUTH_JWT_SECRET must be set when AUTH_PROVIDER=turso")
    return raw.encode("utf-8")


def _issue_token(claims: dict) -> str:
    now = int(time.time())
    header_b64 = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(
        json.dumps({**claims, "iat": now, "exp": now + _TOKEN_TTL_SECONDS}, separators=(",", ":")).encode()
    )
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def _decode_token(token: str) -> dict | None:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected = hmac.new(_secret(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ─── storage ─────────────────────────────────────────────────────────────

def _connect():
    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    if url and token:
        import libsql
        conn = libsql.connect(database=url, auth_token=token)
    else:
        import sqlite3
        db_path = Path(__file__).resolve().parent / "data" / "auth_dev.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS auth_users (
            email TEXT PRIMARY KEY,
            uid TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            branch_ids TEXT NOT NULL,
            permissions TEXT NOT NULL,
            display_name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    return conn


# ─── public API ──────────────────────────────────────────────────────────

def create_user(
    email: str,
    password: str,
    tenant_id: str,
    branch_ids,
    permissions,
    display_name: str | None = None,
    uid: str | None = None,
) -> dict:
    """Creates the user, or replaces them (same email) if they already
    exist — safe to re-run when you just want to change a password or
    permission set."""
    email_norm = email.strip().lower()
    if not email_norm or "@" not in email_norm:
        raise ValueError("invalid email")
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if not tenant_id or not str(tenant_id).strip():
        raise ValueError("tenant_id is required")
    uid = uid or secrets.token_hex(12)
    conn = _connect()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO auth_users
               (email, uid, password_hash, tenant_id, branch_ids, permissions, display_name, active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                email_norm,
                uid,
                _hash_password(password),
                str(tenant_id),
                json.dumps(list(branch_ids)),
                json.dumps(list(permissions)),
                display_name or email_norm,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"uid": uid, "email": email_norm, "tenant_id": str(tenant_id)}


def sign_in(email: str, password: str) -> dict:
    """Returns the {token, tenant_id, account_id, display_name} payload
    AuthService.login expects on the Flutter side, or raises AuthError."""
    email_norm = email.strip().lower()
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT uid, password_hash, tenant_id, branch_ids, permissions, display_name, active "
            "FROM auth_users WHERE email = ?",
            (email_norm,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        _hash_password(password)  # keep timing similar whether or not the email exists
        raise AuthError("بيانات الدخول غير صحيحة.")

    uid, password_hash, tenant_id, branch_ids_json, permissions_json, display_name, active = row
    if not active or not _verify_password(password, password_hash):
        raise AuthError("بيانات الدخول غير صحيحة.")

    claims = {
        "uid": uid,
        "tenant_id": tenant_id,
        "branch_ids": json.loads(branch_ids_json),
        "permissions": json.loads(permissions_json),
    }
    return {
        "token": _issue_token(claims),
        "tenant_id": tenant_id,
        "account_id": uid,
        "display_name": display_name,
    }


def verify_request(request) -> dict | None:
    """Same shape/contract the old production_auth.verify_request had:
    reads `Authorization: Bearer <token>`, returns the claims dict or None
    (=> UNAUTHORIZED) for anything invalid/expired/missing."""
    headers = getattr(request, "headers", None)
    raw = headers.get("authorization") if headers is not None else None
    if not raw or not raw.lower().startswith("bearer "):
        return None
    payload = _decode_token(raw.split(" ", 1)[1].strip())
    if not payload:
        return None
    uid = payload.get("uid")
    tenant_id = payload.get("tenant_id")
    if not uid or not tenant_id:
        return None
    return {
        "uid": str(uid),
        "tenant_id": str(tenant_id),
        "branch_ids": frozenset(str(x) for x in payload.get("branch_ids", ())),
        "permissions": frozenset(str(x) for x in payload.get("permissions", ())),
    }


# ─── admin CLI: create/update a login user ──────────────────────────────
#
#   TURSO_DATABASE_URL=... TURSO_AUTH_TOKEN=... python3 -m backend.api_server.turso_auth \
#       create-user --email owner@example.com --password 'a-strong-password' \
#       --tenant-id shosha-shop --branch-ids main --permissions all
#
# Run from the repo root. Omit TURSO_* to write to a local SQLite file
# instead (matches AUTH_PROVIDER=turso running locally without Turso).

def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Manage Turso-backed auth users.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    create = sub.add_parser("create-user", help="Create or update a login user.")
    create.add_argument("--email", required=True)
    create.add_argument("--password", required=True)
    create.add_argument("--tenant-id", required=True)
    create.add_argument("--branch-ids", required=True, help="Comma-separated branch IDs, e.g. main,branch2")
    create.add_argument("--permissions", default="", help="Comma-separated permission strings, or 'all'")
    create.add_argument("--display-name", default=None)

    args = parser.parse_args()
    if args.cmd == "create-user":
        permissions = (
            ALL_PERMISSIONS
            if args.permissions.strip().lower() == "all"
            else [p.strip() for p in args.permissions.split(",") if p.strip()]
        )
        branch_ids = [b.strip() for b in args.branch_ids.split(",") if b.strip()]
        result = create_user(
            args.email, args.password, args.tenant_id, branch_ids, permissions, args.display_name
        )
        print(f"OK: uid={result['uid']} email={result['email']} tenant_id={result['tenant_id']}")
        print(f"Branches: {branch_ids} | Permissions: {len(permissions)} granted")
        print("Log in from the app now with this email/password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
