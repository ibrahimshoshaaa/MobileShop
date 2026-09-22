"""Durable local SQL store for the Offline-First client.

The local store is an outbox/cache boundary; financial authority remains the
server when Online is enabled. All command writes are tenant/branch scoped and
idempotent.
"""
from __future__ import annotations
import json, sqlite3, threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_ALLOWED = {"PENDING", "APPLIED", "CONFLICT", "FAILED"}

class SQLiteRepository:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS commands (
              command_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
              branch_id TEXT NOT NULL, command TEXT NOT NULL,
              payload TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
              error TEXT, attempts INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS records (
              entity TEXT NOT NULL, record_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL, branch_id TEXT NOT NULL,
              payload TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
              PRIMARY KEY(entity, record_id)
            );
            CREATE TABLE IF NOT EXISTS outbox (
              command_id TEXT PRIMARY KEY REFERENCES commands(command_id) ON DELETE CASCADE,
              next_attempt_at TEXT, last_error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_commands_tenant_status
              ON commands(tenant_id, status, created_at);
            CREATE INDEX IF NOT EXISTS idx_records_tenant_branch
              ON records(tenant_id, branch_id, entity);
            """)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Provide a real local transaction with rollback on exception."""
        with self._lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
            else:
                self.conn.execute("COMMIT")

    def submit_command(self, *, command_id: str, tenant_id: str, branch_id: str,
                       command: str, payload: dict[str, Any]) -> str:
        if not all(isinstance(v, str) and v.strip() for v in (command_id, tenant_id, branch_id, command)):
            raise ValueError("command_id, tenant_id, branch_id and command are required")
        with self.transaction() as db:
            existing = db.execute("SELECT tenant_id, branch_id, status FROM commands WHERE command_id=?",
                                  (command_id,)).fetchone()
            if existing:
                if existing["tenant_id"] != tenant_id or existing["branch_id"] != branch_id:
                    raise ValueError("command_id already belongs to another tenant/branch")
                return str(existing["status"])
            db.execute("INSERT INTO commands(command_id,tenant_id,branch_id,command,payload) VALUES(?,?,?,?,?)",
                       (command_id, tenant_id, branch_id, command,
                        json.dumps(payload, ensure_ascii=False, sort_keys=True)))
            db.execute("INSERT INTO outbox(command_id) VALUES(?)", (command_id,))
            return "PENDING"

    def mark_command(self, command_id: str, status: str, error: str | None = None) -> None:
        if status not in _ALLOWED:
            raise ValueError("invalid command status")
        with self.transaction() as db:
            db.execute("UPDATE commands SET status=?, error=?, updated_at=CURRENT_TIMESTAMP WHERE command_id=?",
                       (status, error, command_id))
            if status in {"APPLIED", "CONFLICT", "FAILED"}:
                db.execute("DELETE FROM outbox WHERE command_id=?", (command_id,))

    def record_attempt(self, command_id: str, error: str | None = None) -> None:
        with self.transaction() as db:
            db.execute("UPDATE commands SET attempts=attempts+1, error=?, updated_at=CURRENT_TIMESTAMP WHERE command_id=?",
                       (error, command_id))
            db.execute("UPDATE outbox SET last_error=? WHERE command_id=?", (error, command_id))

    def pending_commands(self, tenant_id: str, branch_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        sql = """SELECT c.*, o.last_error FROM commands c JOIN outbox o USING(command_id)
                 WHERE c.tenant_id=? AND c.status='PENDING'"""
        args: list[Any] = [tenant_id]
        if branch_id is not None:
            sql += " AND c.branch_id=?"
            args.append(branch_id)
        sql += " ORDER BY c.created_at, c.command_id LIMIT ?"
        args.append(limit)
        rows = self.conn.execute(sql, args).fetchall()
        return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def upsert_record(self, *, entity: str, record_id: str, tenant_id: str,
                      branch_id: str, payload: dict[str, Any], expected_version: int | None = None) -> int:
        """Atomically insert/update a scoped local projection with optimistic concurrency."""
        if not all(isinstance(v, str) and v.strip() for v in (entity, record_id, tenant_id, branch_id)):
            raise ValueError("entity, record_id, tenant_id and branch_id are required")
        with self.transaction() as db:
            current = db.execute(
                "SELECT tenant_id, branch_id, version FROM records WHERE entity=? AND record_id=?",
                (entity, record_id)).fetchone()
            if current:
                if current["tenant_id"] != tenant_id or current["branch_id"] != branch_id:
                    raise ValueError("record belongs to another tenant/branch")
                if expected_version is not None and current["version"] != expected_version:
                    raise ValueError("STALE_VERSION")
                version = int(current["version"]) + 1
                db.execute("UPDATE records SET payload=?, version=? WHERE entity=? AND record_id=?",
                           (json.dumps(payload, ensure_ascii=False, sort_keys=True), version, entity, record_id))
                return version
            if expected_version not in (None, 0):
                raise ValueError("STALE_VERSION")
            db.execute("INSERT INTO records(entity,record_id,tenant_id,branch_id,payload,version) VALUES(?,?,?,?,?,1)",
                       (entity, record_id, tenant_id, branch_id,
                        json.dumps(payload, ensure_ascii=False, sort_keys=True)))
            return 1

    def get_record(self, *, entity: str, record_id: str, tenant_id: str, branch_id: str | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM records WHERE entity=? AND record_id=? AND tenant_id=?"
        args: list[Any] = [entity, record_id, tenant_id]
        if branch_id is not None:
            sql += " AND branch_id=?"
            args.append(branch_id)
        row = self.conn.execute(sql, args).fetchone()
        if not row:
            return None
        return dict(row) | {"payload": json.loads(row["payload"])}

    def list_records(self, *, tenant_id: str, branch_id: str | None = None,
                     entity: str | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        sql = "SELECT * FROM records WHERE tenant_id=?"
        args: list[Any] = [tenant_id]
        if branch_id is not None:
            sql += " AND branch_id=?"; args.append(branch_id)
        if entity is not None:
            sql += " AND entity=?"; args.append(entity)
        sql += " ORDER BY entity, record_id LIMIT ?"; args.append(limit)
        rows = self.conn.execute(sql, args).fetchall()
        return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]
