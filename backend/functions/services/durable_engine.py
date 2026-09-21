"""Durable ERP command engine backed by SQLite/libSQL."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from backend.functions.persistence.domain_serializer import deserialize_value, serialize_value
from backend.functions.services.erp_engine import ERPCommandEngine


class DurableERPCommandEngine(ERPCommandEngine):
    def __init__(self, db_path: str | Path = "erp_durable.db", connection=None):
        super().__init__()
        self._db_path = Path(db_path)
        self._remote = connection is not None
        self._transaction_depth = 0
        if connection is not None:
            self._conn = connection
        else:
            import os
            url = os.getenv("TURSO_DATABASE_URL")
            token = os.getenv("TURSO_AUTH_TOKEN")
            if url and token:
                try:
                    import libsql
                except ImportError as exc:
                    raise RuntimeError("libsql is required when TURSO_DATABASE_URL is configured") from exc
                self._conn = libsql.connect(database=url, auth_token=token)
                self._remote = True
            else:
                self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("""CREATE TABLE IF NOT EXISTS records (
            repo TEXT NOT NULL, record_id TEXT NOT NULL, payload TEXT NOT NULL,
            tenant_id TEXT NOT NULL DEFAULT 'legacy', PRIMARY KEY (repo, record_id)
        )""")
        self._conn.commit()
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(records)").fetchall()}
        if "tenant_id" not in columns:
            self._conn.execute("ALTER TABLE records ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'legacy'")
            self._conn.commit()
        self._reload()

    @property
    def connection(self):
        """Underlying DB handle for components sharing this transaction boundary."""
        return self._conn

    def _repo_attrs(self) -> dict:
        return {name: value for name, value in self.__dict__.items() if hasattr(value, "_data")}

    def _reload(self, clear: bool = False) -> None:
        if clear:
            for repo in self._repo_attrs().values():
                repo._data.clear()
                repo._tenant_by_id.clear()
            self._processed.clear()
        for repo_name, record_id, payload, tenant_id in self._conn.execute(
            "SELECT repo, record_id, payload, tenant_id FROM records"
        ).fetchall():
            value = deserialize_value(json.loads(payload))
            if repo_name == "_processed":
                self._processed[record_id] = value
                continue
            repo = getattr(self, repo_name, None)
            if repo is not None and hasattr(repo, "_data"):
                repo._data[record_id] = value
                repo._tenant_by_id[record_id] = tenant_id

    def transaction(self, fn):
        # Dispatch calls transaction() too. When a sync upload supplies this
        # method as its transaction runner, nested calls must participate in
        # the outer transaction rather than committing independently.
        if self._transaction_depth:
            return fn()
        with self._lock:
            began = False
            self._transaction_depth = 1
            try:
                for attempt in range(5):
                    try:
                        self._conn.execute("BEGIN IMMEDIATE")
                        began = True
                        break
                    except Exception:
                        if attempt == 4:
                            raise
                        time.sleep(0.05 * (attempt + 1))
                if not began:
                    raise RuntimeError("unable to begin durable transaction")
                if self._remote:
                    self._reload(clear=True)
                before_repos = self._repo_attrs()
                before = {name: dict(repo._data) for name, repo in before_repos.items()}
                before_tenants = {name: dict(repo._tenant_by_id) for name, repo in before_repos.items()}
                processed_before = dict(self._processed)
                result = super().transaction(fn)
                self._persist_changes(before, processed_before, commit=False)
                self._conn.commit()
                return result
            except Exception:
                self._conn.rollback()
                if "before" in locals():
                    for name, repo in self._repo_attrs().items():
                        repo._data = dict(before.get(name, {}))
                        repo._tenant_by_id = dict(before_tenants.get(name, {}))
                    self._processed = dict(processed_before)
                raise
            finally:
                self._transaction_depth = 0

    def _persist_changes(self, before: dict, processed_before: dict, commit: bool = True):
        cur = self._conn.cursor()
        for name, repo in self._repo_attrs().items():
            old = before.get(name, {})
            for record_id, value in repo._data.items():
                if record_id not in old or old[record_id] is not value:
                    cur.execute("INSERT OR REPLACE INTO records (repo, record_id, payload, tenant_id) VALUES (?, ?, ?, ?)",
                                (name, record_id, json.dumps(serialize_value(value)), repo.tenant_of(record_id) or "legacy"))
        for name, old_repo in before.items():
            current_repo = self._repo_attrs().get(name)
            if current_repo is not None:
                for record_id in set(old_repo) - set(current_repo._data):
                    cur.execute("DELETE FROM records WHERE repo = ? AND record_id = ?", (name, record_id))
        for command_id, value in self._processed.items():
            if command_id not in processed_before or processed_before[command_id] is not value:
                cur.execute("INSERT OR REPLACE INTO records (repo, record_id, payload, tenant_id) VALUES (?, ?, ?, ?)",
                            ("_processed", command_id, json.dumps(serialize_value(value)), command_id.split(":", 1)[0] if ":" in command_id else "legacy"))
        for command_id in set(processed_before) - set(self._processed):
            cur.execute("DELETE FROM records WHERE repo = ? AND record_id = ?", ("_processed", command_id))
        if commit:
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
