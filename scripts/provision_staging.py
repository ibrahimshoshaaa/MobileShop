#!/usr/bin/env python3
"""Provision an isolated Turso staging principal for the smoke test.

Run locally only. Never commit Turso tokens or staging passwords.
The script creates a small, deterministic tenant/branch dataset and a
turso_auth login user with the permissions required by the authenticated
staging smoke test.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import libsql_client

from backend.api_server import turso_auth

TENANT_ID = os.getenv("STAGING_TENANT_ID", "staging-tenant")
BRANCH_ID = os.getenv("STAGING_BRANCH_ID", "staging-main")
STAGING_EMAIL = os.getenv("STAGING_EMAIL", "staging-smoke@example.com")
STAGING_PASSWORD = os.getenv("STAGING_PASSWORD")
DB_URL = os.getenv("TURSO_DATABASE_URL")
DB_TOKEN = os.getenv("TURSO_AUTH_TOKEN")


def required(name: str, value: str | None) -> str:
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def insert_record(conn, repo: str, record_id: str, payload: dict, tenant_id: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO records (repo, record_id, payload, tenant_id) VALUES (?, ?, ?, ?)",
        (repo, record_id, json.dumps(payload, separators=(",", ":")), tenant_id),
    )


def main() -> int:
    password = required("STAGING_PASSWORD", STAGING_PASSWORD)
    db_url = required("TURSO_DATABASE_URL", DB_URL)
    db_token = required("TURSO_AUTH_TOKEN", DB_TOKEN)

    # libsql-client is a pure-Python client that can use Turso's HTTP endpoint,
    # which makes this provisioning script usable from Termux/Android where the
    # Rust-backed libsql package does not provide a compatible wheel.
    http_url = db_url.replace("libsql://", "https://", 1)
    with libsql_client.create_client_sync(http_url, auth_token=db_token) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS records (
                repo TEXT NOT NULL,
                record_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT 'legacy',
                PRIMARY KEY (repo, record_id)
            )"""
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(records)").rows}
        if "tenant_id" not in columns:
            conn.execute("ALTER TABLE records ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'legacy'")

        def dc(name: str, fields: dict) -> dict:
            return {"__dataclass__": name, "fields": fields}

        def dec(value: str) -> dict:
            return {"__decimal__": value}

        insert_record(
            conn, "branches", BRANCH_ID,
            dc("Branch", {"id": BRANCH_ID, "name": "Staging Branch", "code": "STG", "active": True, "tenant_id": TENANT_ID}),
            TENANT_ID,
        )
        insert_record(
            conn, "products", "staging-product-1",
            dc("Product", {
                "id": "staging-product-1", "name": "Staging Test Phone", "sku": "STAGING-001",
                "product_type": "PHONE", "barcode": "STAGING-001", "selling_price": dec("1000"),
                "default_cost": dec("600"), "warranty_days": 365, "reorder_level": dec("1"),
                "active": True, "tenant_id": TENANT_ID,
            }),
            TENANT_ID,
        )
        insert_record(
            conn, "stock", "staging-stock-1",
            dc("StockMovement", {
                "id": "staging-stock-1", "branch_id": BRANCH_ID, "product_id": "staging-product-1",
                "quantity": dec("10"), "movement_type": "OPENING_BALANCE", "reference_id": "staging-bootstrap",
                "unit_id": None, "cost": dec("600"),
                "created_at": {"__datetime__": "2026-01-01T00:00:00+00:00"}, "tenant_id": TENANT_ID,
            }),
            TENANT_ID,
        )
        insert_record(
            conn, "wallets", "staging-wallet-cash",
            dc("Wallet", {"id": "staging-wallet-cash", "branch_id": BRANCH_ID, "name": "Staging Cash", "wallet_type": "CASH", "active": True, "tenant_id": TENANT_ID}),
            TENANT_ID,
        )
        insert_record(
            conn, "customers", "staging-customer-1",
            dc("Customer", {"id": "staging-customer-1", "name": "Staging Test Customer", "phone": "0000000000", "active": True, "tenant_id": TENANT_ID}),
            TENANT_ID,
        )

    result = turso_auth.create_user(
        email=STAGING_EMAIL,
        password=password,
        tenant_id=TENANT_ID,
        branch_ids=[BRANCH_ID],
        permissions=["inventory.read"],
        display_name="Staging Smoke",
    )

    print(f"Provisioned staging user uid={result['uid']} email={result['email']}")
    print(f"STAGING_TENANT_ID={TENANT_ID}")
    print(f"STAGING_BRANCH_ID={BRANCH_ID}")
    print("Claims assigned: tenant_id, branch_ids, permissions=[inventory.read]")
    print("Next: POST /auth/login with STAGING_EMAIL/STAGING_PASSWORD to obtain a fresh token.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
