"""Small SQLite persistence layer for offline-first device state.

Secrets are deliberately excluded: only non-sensitive account metadata and
sync commands are stored locally. Passwords/tokens belong to an auth provider
and secure OS storage, not this database.
"""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from typing import Any

class LocalStore:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS device_profile (
            id INTEGER PRIMARY KEY CHECK (id=1),
            sync_mode TEXT NOT NULL CHECK(sync_mode IN ('offline','online')),
            account_id TEXT, email TEXT, tenant_id TEXT,
            branch_ids_json TEXT NOT NULL DEFAULT '[]',
            access_token_ref TEXT
        );
        CREATE TABLE IF NOT EXISTS sync_operations (
            command_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('PENDING','APPLIED','CONFLICT','FAILED')),
            error_code TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TEXT
        );
        """)
        self.db.commit()
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(sync_operations)").fetchall()}
        if "attempts" not in columns:
            self.db.execute("ALTER TABLE sync_operations ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        if "next_attempt_at" not in columns:
            self.db.execute("ALTER TABLE sync_operations ADD COLUMN next_attempt_at TEXT")
        self.db.commit()

    def set_mode(self, mode: str) -> None:
        if mode not in {"offline", "online"}: raise ValueError("invalid sync mode")
        self.db.execute("INSERT INTO device_profile(id,sync_mode) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET sync_mode=excluded.sync_mode", (mode,))
        self.db.commit()

    def link_account(self, *, account_id: str, email: str, tenant_id: str, branch_ids: list[str], access_token_ref: str | None = None) -> None:
        if not account_id or not tenant_id or not branch_ids: raise ValueError("account and at least one branch are required")
        self.db.execute("""INSERT INTO device_profile(id,sync_mode,account_id,email,tenant_id,branch_ids_json,access_token_ref)
        VALUES(1,'online',?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET sync_mode='online',account_id=excluded.account_id,email=excluded.email,tenant_id=excluded.tenant_id,branch_ids_json=excluded.branch_ids_json,access_token_ref=excluded.access_token_ref""",
        (account_id,email.strip().lower(),tenant_id,json.dumps(sorted(set(branch_ids))),access_token_ref))
        self.db.commit()

    def profile(self) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM device_profile WHERE id=1").fetchone()
        if not row: return None
        result = dict(row); result["branch_ids"] = json.loads(result.pop("branch_ids_json")); return result

    def enqueue(self, command_id: str, payload: dict[str, Any]) -> None:
        if not command_id: raise ValueError("command_id is required")
        self.db.execute("INSERT OR IGNORE INTO sync_operations(command_id,payload_json,status) VALUES(?,?, 'PENDING')", (command_id,json.dumps(payload,sort_keys=True)))
        self.db.commit()

    def pending(self) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT command_id,payload_json,status FROM sync_operations WHERE status='PENDING' AND (next_attempt_at IS NULL OR next_attempt_at <= CURRENT_TIMESTAMP) ORDER BY rowid").fetchall()
        return [{"command_id": r["command_id"], "payload": json.loads(r["payload_json"]), "status": r["status"]} for r in rows]

    def mark_retry(self, command_id: str, error_code: str, next_attempt_at: str) -> None:
        self.db.execute(
            "UPDATE sync_operations SET error_code=?, attempts=attempts+1, next_attempt_at=? WHERE command_id=?",
            (error_code, next_attempt_at, command_id),
        )
        self.db.commit()

    def mark(self, command_id: str, status: str, error_code: str | None = None) -> None:
        if status not in {"APPLIED","CONFLICT","FAILED"}: raise ValueError("invalid terminal status")
        self.db.execute("UPDATE sync_operations SET status=?,error_code=? WHERE command_id=?", (status,error_code,command_id)); self.db.commit()

    def clear_account(self) -> None:
        """Safely unlink the cloud account without deleting offline business data."""
        self.db.execute("UPDATE device_profile SET sync_mode='offline', account_id=NULL, email=NULL, tenant_id=NULL, branch_ids_json='[]', access_token_ref=NULL WHERE id=1")
        self.db.commit()

    def enqueue_scoped(self, command_id: str, tenant_id: str, branch_id: str, payload: dict[str, Any]) -> None:
        """Queue only tenant/branch-scoped commands; prevents cross-account replay."""
        profile = self.profile()
        if not profile or profile.get('sync_mode') != 'online' or profile.get('tenant_id') != tenant_id:
            raise ValueError('account is not linked to this tenant')
        if branch_id not in profile.get('branch_ids', []):
            raise ValueError('branch is not assigned to linked account')
        envelope = dict(payload)
        envelope['_tenant_id'] = tenant_id
        envelope['_branch_id'] = branch_id
        self.enqueue(command_id, envelope)
