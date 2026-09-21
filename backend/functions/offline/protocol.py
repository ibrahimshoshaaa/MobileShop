from __future__ import annotations

import hashlib
import json
import os
import time
import sqlite3
from threading import RLock
from pathlib import Path
from typing import Callable, Iterable

from shared.contracts.errors import DomainError


_CONFLICT_CODES = {"STALE_VERSION", "TRANSACTION_CONFLICT", "ACCOUNT_SCOPE_MISMATCH"}
_RETRYABLE_CODES = {"TEMPORARY_UNAVAILABLE", "DB_BUSY", "NETWORK_ERROR"}


class SyncProtocol:
    """Server-side offline sync protocol.

    Upload is idempotent by (tenant, branch, command_id). Every successful
    command becomes an append-only event with a monotonic cursor. Download is
    cursor-based and tenant/branch filtered. A stale expected_version is a
    conflict, never an implicit overwrite.
    """

    def __init__(self, path: str | Path = "sync_protocol.db", connection=None):
        if connection is not None:
            self.db = connection
        else:
            url, token = os.getenv("TURSO_DATABASE_URL"), os.getenv("TURSO_AUTH_TOKEN")
            if url and token:
                try:
                    import libsql
                except ImportError as exc:
                    raise RuntimeError("libsql is required for remote sync storage") from exc
                self.db = libsql.connect(database=url, auth_token=token)
            else:
                self.db = sqlite3.connect(str(path), check_same_thread=False)
        if isinstance(self.db, sqlite3.Connection):
            self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS sync_receipts (
            tenant_id TEXT NOT NULL,
            branch_id TEXT NOT NULL,
            command_id TEXT NOT NULL,
            status TEXT NOT NULL,
            result_json TEXT,
            error_code TEXT,
            request_hash TEXT,
            claimed_at REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (tenant_id, branch_id, command_id)
        );
        CREATE TABLE IF NOT EXISTS sync_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            branch_id TEXT NOT NULL,
            command_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_sync_events_scope
            ON sync_events(tenant_id, branch_id, seq);
        """)
        self.db.commit()
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(sync_receipts)").fetchall()}
        if "request_hash" not in columns:
            self.db.execute("ALTER TABLE sync_receipts ADD COLUMN request_hash TEXT")
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(sync_receipts)").fetchall()}
        if "claimed_at" not in columns:
            self.db.execute("ALTER TABLE sync_receipts ADD COLUMN claimed_at REAL")
        self.db.commit()
        self._lock = RLock()

    def upload(self, envelopes: Iterable[dict], *, tenant_id: str, branch_id: str,
               executor: Callable[[dict], object], limit: int = 100) -> dict:
        with self._lock:
            return self._upload_locked(envelopes, tenant_id=tenant_id, branch_id=branch_id, executor=executor, limit=limit)

    def _upload_locked(self, envelopes, *, tenant_id: str, branch_id: str,
                       executor: Callable[[dict], object], limit: int = 100):
        envelopes = list(envelopes)
        if len(envelopes) > limit:
            raise DomainError("SYNC_BATCH_TOO_LARGE", "دفعة المزامنة كبيرة جداً.", {"limit": limit})
        results = []
        for envelope in envelopes:
            command_id = str(envelope.get("command_id", "")).strip()
            env_tenant = envelope.get("tenant_id")
            env_branch = envelope.get("branch_id")
            if not command_id or env_tenant != tenant_id or env_branch != branch_id:
                results.append({"command_id": command_id, "status": "CONFLICT", "error_code": "ACCOUNT_SCOPE_MISMATCH"})
                continue

            request_hash = hashlib.sha256(json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()
            row = self.db.execute(
                "SELECT status,result_json,error_code,request_hash FROM sync_receipts WHERE tenant_id=? AND branch_id=? AND command_id=?",
                (tenant_id, branch_id, command_id),
            ).fetchone()
            if row:
                if row[3] and row[3] != request_hash:
                    results.append({"command_id": command_id, "status": "CONFLICT", "error_code": "IDEMPOTENCY_KEY_REUSE"})
                    continue
                results.append({
                    "command_id": command_id, "status": row[0],
                    "result": json.loads(row[1]) if row[1] else None,
                    "error_code": row[2],
                    "idempotent_replay": True,
                })
                continue

            try:
                # Claim the command before executing it. The claim is committed
                # separately so two API workers cannot both execute the same
                # command before either one writes its final receipt.
                self.db.execute(
                    "INSERT INTO sync_receipts(tenant_id,branch_id,command_id,status,request_hash,claimed_at) VALUES(?,?,?,?,?,?)",
                    (tenant_id, branch_id, command_id, "PROCESSING", request_hash, time.time()),
                )
                self.db.commit()
            except sqlite3.IntegrityError:
                row = self.db.execute(
                    "SELECT status,result_json,error_code,request_hash,claimed_at FROM sync_receipts WHERE tenant_id=? AND branch_id=? AND command_id=?",
                    (tenant_id, branch_id, command_id),
                ).fetchone()
                if row and row[3] == request_hash:
                    if row[0] == "PROCESSING" and row[4] and time.time() - float(row[4]) > 60:
                        self.db.execute("DELETE FROM sync_receipts WHERE tenant_id=? AND branch_id=? AND command_id=?", (tenant_id, branch_id, command_id))
                        self.db.commit()
                    else:
                        results.append({"command_id": command_id, "status": row[0], "result": json.loads(row[1]) if row[1] else None, "error_code": row[2], "retryable": row[0] == "PROCESSING"})
                        continue
                else:
                    results.append({"command_id": command_id, "status": "CONFLICT", "error_code": "IDEMPOTENCY_KEY_REUSE"})
                continue

            try:
                result = executor(envelope)
                result_json = json.dumps(result, default=str, ensure_ascii=False, sort_keys=True)
                self.db.execute(
                    "UPDATE sync_receipts SET status='APPLIED', result_json=?, error_code=NULL, claimed_at=NULL WHERE tenant_id=? AND branch_id=? AND command_id=?",
                    (result_json, tenant_id, branch_id, command_id),
                )
                self.db.execute(
                    "INSERT INTO sync_events(tenant_id,branch_id,command_id,event_type,payload_json) VALUES(?,?,?,?,?)",
                    (tenant_id, branch_id, command_id, "COMMAND_APPLIED", result_json),
                )
                self.db.commit()
                results.append({"command_id": command_id, "status": "APPLIED", "result": json.loads(result_json)})
            except DomainError as exc:
                code = exc.code
                status = "CONFLICT" if code in _CONFLICT_CODES else "FAILED"
                self.db.execute(
                    "UPDATE sync_receipts SET status=?, error_code=?, result_json=NULL, claimed_at=NULL WHERE tenant_id=? AND branch_id=? AND command_id=?",
                    (status, code, tenant_id, branch_id, command_id),
                )
                self.db.commit()
                results.append({"command_id": command_id, "status": status, "error_code": code})
            except Exception:
                # Keep the receipt retryable after infrastructure failure; the
                # executor may already have committed in another system, so callers
                # must use the ERP command idempotency key when retrying.
                self.db.execute(
                    "UPDATE sync_receipts SET status='RETRYABLE', error_code='TEMPORARY_UNAVAILABLE', claimed_at=NULL WHERE tenant_id=? AND branch_id=? AND command_id=?",
                    (tenant_id, branch_id, command_id),
                )
                self.db.commit()
                results.append({"command_id": command_id, "status": "RETRYABLE", "error_code": "TEMPORARY_UNAVAILABLE"})

        cursor = self.db.execute(
            "SELECT COALESCE(MAX(seq),0) FROM sync_events WHERE tenant_id=? AND branch_id=?",
            (tenant_id, branch_id),
        ).fetchone()[0]
        return {"results": results, "next_cursor": int(cursor)}

    def download(self, *, tenant_id: str, branch_id: str, cursor: int = 0, limit: int = 100) -> dict:
        if cursor < 0 or limit < 1 or limit > 1000:
            raise ValueError("invalid cursor or limit")
        rows = self.db.execute(
            """SELECT seq,command_id,event_type,payload_json,created_at
               FROM sync_events
               WHERE tenant_id=? AND branch_id=? AND seq>?
               ORDER BY seq LIMIT ?""",
            (tenant_id, branch_id, cursor, limit),
        ).fetchall()
        changes = [{
            "cursor": int(r[0]), "command_id": r[1], "event_type": r[2],
            "payload": json.loads(r[3]), "created_at": r[4],
        } for r in rows]
        next_cursor = changes[-1]["cursor"] if changes else cursor
        return {"changes": changes, "next_cursor": next_cursor, "has_more": len(changes) == limit}

    def close(self):
        self.db.close()
