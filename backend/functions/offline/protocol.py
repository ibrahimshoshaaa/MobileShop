from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import sqlite3
from threading import RLock
from pathlib import Path
from typing import Callable, Iterable

from shared.contracts.errors import DomainError


logger = logging.getLogger(__name__)

_CONFLICT_CODES = {"STALE_VERSION", "TRANSACTION_CONFLICT", "ACCOUNT_SCOPE_MISMATCH"}
_RETRYABLE_CODES = {"TEMPORARY_UNAVAILABLE", "DB_BUSY", "NETWORK_ERROR"}


class SyncProtocol:
    """Server-side offline sync protocol.

    When a connection is supplied, the caller owns its lifecycle. The API
    server passes the DurableERPCommandEngine connection so a command's
    business mutation and its sync receipt/event are committed atomically.
    """

    def __init__(self, path: str | Path = "sync_protocol.db", connection=None):
        self._owns_connection = connection is None
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

    def _request_hash(self, envelope: dict) -> str:
        return hashlib.sha256(
            json.dumps(
                envelope, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, default=str,
            ).encode()
        ).hexdigest()

    def _read_receipt(self, tenant_id: str, branch_id: str, command_id: str):
        return self.db.execute(
            "SELECT status,result_json,error_code,request_hash,claimed_at "
            "FROM sync_receipts WHERE tenant_id=? AND branch_id=? AND command_id=?",
            (tenant_id, branch_id, command_id),
        ).fetchone()

    def _replay_result(self, command_id: str, row, *, idempotent_replay: bool = True) -> dict:
        return {
            "command_id": command_id,
            "status": row[0],
            "result": json.loads(row[1]) if row[1] else None,
            "error_code": row[2],
            "retryable": row[0] == "PROCESSING",
            "idempotent_replay": idempotent_replay,
        }

    def _begin(self) -> None:
        for attempt in range(5):
            try:
                self.db.execute("BEGIN")
                return
            except Exception as exc:
                message = str(exc)
                if "SQLITE_BUSY" not in message and "database is locked" not in message:
                    raise
                if attempt == 4:
                    raise DomainError("DB_BUSY", "قاعدة البيانات مشغولة مؤقتاً.", {}) from exc
                time.sleep(0.05 * (attempt + 1))

    def _upload_locked(self, envelopes, *, tenant_id: str, branch_id: str,
                       executor: Callable[[dict], object], limit: int = 100):
        envelopes = list(envelopes)
        if len(envelopes) > limit:
            raise DomainError("SYNC_BATCH_TOO_LARGE", "دفعة المزامنة كبيرة جداً.", {"limit": limit})

        results = []
        processing_lease_seconds = 600

        for envelope in envelopes:
            command_id = str(envelope.get("command_id", "")).strip()
            if not command_id or envelope.get("tenant_id") != tenant_id or envelope.get("branch_id") != branch_id:
                results.append({
                    "command_id": command_id,
                    "status": "CONFLICT",
                    "error_code": "ACCOUNT_SCOPE_MISMATCH",
                })
                continue

            request_hash = self._request_hash(envelope)
            row = self._read_receipt(tenant_id, branch_id, command_id)
            if row:
                if row[3] and row[3] != request_hash:
                    results.append({
                        "command_id": command_id,
                        "status": "CONFLICT",
                        "error_code": "IDEMPOTENCY_KEY_REUSE",
                    })
                    continue
                if row[0] != "PROCESSING":
                    results.append(self._replay_result(command_id, row))
                    continue

                # A PROCESSING claim is a committed lease, not an open DB
                # transaction. Wait for the owner briefly; reclaim only when
                # the lease is genuinely stale.
                claimed_at = float(row[4] or 0)
                if claimed_at and time.time() - claimed_at <= processing_lease_seconds:
                    results.append(self._replay_result(command_id, row))
                    continue

                self._begin()
                try:
                    updated = self.db.execute(
                        "UPDATE sync_receipts SET claimed_at=? "
                        "WHERE tenant_id=? AND branch_id=? AND command_id=? "
                        "AND status='PROCESSING' AND claimed_at=?",
                        (time.time(), tenant_id, branch_id, command_id, row[4]),
                    ).rowcount
                    self.db.commit()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        logger.debug("sync reclaim rollback failed", exc_info=True)
                    raise
                if not updated:
                    fresh = self._read_receipt(tenant_id, branch_id, command_id)
                    results.append(self._replay_result(command_id, fresh) if fresh else {
                        "command_id": command_id,
                        "status": "RETRYABLE",
                        "error_code": "TEMPORARY_UNAVAILABLE",
                    })
                    continue
            else:
                # Claim first and commit it before running application code.
                # This is critical for Turso: holding an interactive write
                # transaction open while another client competes can trigger
                # SQLITE_BUSY and roll back the winning transaction.
                claimed = False
                self._begin()
                try:
                    self.db.execute(
                        "INSERT INTO sync_receipts"
                        "(tenant_id,branch_id,command_id,status,request_hash,claimed_at)"
                        " VALUES(?,?,?,?,?,?)",
                        (tenant_id, branch_id, command_id, "PROCESSING", request_hash, time.time()),
                    )
                    self.db.commit()
                    claimed = True
                except Exception as exc:
                    try:
                        self.db.rollback()
                    except Exception:
                        logger.debug("sync claim rollback failed", exc_info=True)

                    message = str(exc).upper()
                    if "UNIQUE" not in message and "CONSTRAINT" not in message and "SQLITE_BUSY" not in message and "DATABASE IS LOCKED" not in message:
                        raise

                    # Another worker may have won the claim. Give Turso a short
                    # window to expose that committed receipt before replaying.
                    for _ in range(20):
                        time.sleep(0.1)
                        fresh = self._read_receipt(tenant_id, branch_id, command_id)
                        if fresh:
                            if fresh[3] and fresh[3] != request_hash:
                                results.append({
                                    "command_id": command_id,
                                    "status": "CONFLICT",
                                    "error_code": "IDEMPOTENCY_KEY_REUSE",
                                })
                            else:
                                results.append(self._replay_result(command_id, fresh))
                            break
                    else:
                        results.append({
                            "command_id": command_id,
                            "status": "RETRYABLE",
                            "error_code": "TEMPORARY_UNAVAILABLE",
                        })
                    continue

                if not claimed:
                    continue

            try:
                result = executor(envelope)
                result_json = json.dumps(result, default=str, ensure_ascii=False, sort_keys=True)

                self._begin()
                try:
                    updated = self.db.execute(
                        "UPDATE sync_receipts SET status='APPLIED', result_json=?, "
                        "error_code=NULL, claimed_at=NULL "
                        "WHERE tenant_id=? AND branch_id=? AND command_id=? "
                        "AND status='PROCESSING' AND request_hash=?",
                        (result_json, tenant_id, branch_id, command_id, request_hash),
                    ).rowcount
                    if updated != 1:
                        self.db.rollback()
                        fresh = self._read_receipt(tenant_id, branch_id, command_id)
                        results.append(self._replay_result(command_id, fresh) if fresh else {
                            "command_id": command_id,
                            "status": "RETRYABLE",
                            "error_code": "TEMPORARY_UNAVAILABLE",
                        })
                        continue
                    self.db.execute(
                        "INSERT INTO sync_events"
                        "(tenant_id,branch_id,command_id,event_type,payload_json)"
                        " VALUES(?,?,?,?,?)",
                        (tenant_id, branch_id, command_id, "COMMAND_APPLIED", result_json),
                    )
                    self.db.commit()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        logger.debug("sync apply rollback failed", exc_info=True)
                    raise

                results.append({
                    "command_id": command_id,
                    "status": "APPLIED",
                    "result": json.loads(result_json),
                })
            except DomainError as exc:
                status = "CONFLICT" if exc.code in _CONFLICT_CODES else "FAILED"
                self._begin()
                try:
                    self.db.execute(
                        "UPDATE sync_receipts SET status=?, result_json=NULL, error_code=?, claimed_at=NULL "
                        "WHERE tenant_id=? AND branch_id=? AND command_id=? AND status='PROCESSING' "
                        "AND request_hash=?",
                        (status, exc.code, tenant_id, branch_id, command_id, request_hash),
                    )
                    self.db.commit()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        logger.debug("sync failure rollback failed", exc_info=True)
                    raise
                results.append({"command_id": command_id, "status": status, "error_code": exc.code})
            except Exception:
                try:
                    self.db.rollback()
                except Exception:
                    logger.debug("sync rollback failed", exc_info=True)

                self._begin()
                try:
                    self.db.execute(
                        "UPDATE sync_receipts SET status='RETRYABLE', result_json=NULL, "
                        "error_code='TEMPORARY_UNAVAILABLE', claimed_at=NULL "
                        "WHERE tenant_id=? AND branch_id=? AND command_id=? AND status='PROCESSING' "
                        "AND request_hash=?",
                        (tenant_id, branch_id, command_id, request_hash),
                    )
                    self.db.commit()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception:
                        logger.debug("sync retry rollback failed", exc_info=True)
                    raise
                results.append({
                    "command_id": command_id,
                    "status": "RETRYABLE",
                    "error_code": "TEMPORARY_UNAVAILABLE",
                })

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
        if self._owns_connection:
            self.db.close()
