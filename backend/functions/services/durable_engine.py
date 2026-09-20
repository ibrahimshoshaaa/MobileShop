"""Adds real SQLite-backed durability to ERPCommandEngine, without changing
erp_engine.py or completion.py at all.

Approach: `DurableERPCommandEngine.transaction()` wraps the inherited
`transaction()` (installed by completion.py). The base implementation
already does correct atomic rollback-on-exception for the in-memory
Repository dicts — that logic is untouched. This subclass only adds a step
*after* a transaction has already succeeded: diff every repository's
current state against a snapshot taken before the transaction ran, and
write whatever changed to a local SQLite table. On construction, everything
previously written is reloaded back into the in-memory repositories before
the engine is used.

This directly answers two items in the project status doc's "Partially
implemented" list: a persistent repository implementation, and persistent
idempotency records (the `_processed` dict is persisted the same way).

Still explicitly NOT what the status doc means by "Turso/libSQL connection
management" — this is a single local SQLite file for one process, not a
managed remote database, and there is still no multi-server coordination.
It is, however, a real, working step from "resets on every restart" to
"survives restarts on this machine" — see backend/api_server/README.md for
how this fits with the rest of what's still missing.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.functions.persistence.domain_serializer import deserialize_value, serialize_value
from backend.functions.services.erp_engine import ERPCommandEngine


class DurableERPCommandEngine(ERPCommandEngine):
    def __init__(self, db_path: str | Path = "erp_durable.db", connection=None):
        super().__init__()
        self._db_path = Path(db_path)
        self._remote = connection is not None
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
                self._conn = libsql.connect(url, auth_token=token)
                self._remote = True
            else:
                self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                repo TEXT NOT NULL,
                record_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT 'legacy',
                PRIMARY KEY (repo, record_id)
            )
            """
        )
        self._conn.commit()
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(records)").fetchall()}
        if "tenant_id" not in columns:
            self._conn.execute("ALTER TABLE records ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'legacy'")
            self._conn.commit()
        self._reload()

    def _repo_attrs(self) -> dict:
        return {name: value for name, value in self.__dict__.items() if hasattr(value, "_data")}

    def _reload(self, clear: bool = False) -> None:
        if clear:
            for repo in self._repo_attrs().values():
                repo._data.clear()
                repo._tenant_by_id.clear()
            self._processed.clear()
        cur = self._conn.execute("SELECT repo, record_id, payload, tenant_id FROM records")
        for repo_name, record_id, payload, tenant_id in cur.fetchall():
            value = deserialize_value(json.loads(payload))
            if repo_name == "_processed":
                self._processed[record_id] = value
                continue
            repo = getattr(self, repo_name, None)
            if repo is not None and hasattr(repo, "_data"):
                repo._data[record_id] = value
                repo._tenant_by_id[record_id] = tenant_id

    def transaction(self, fn):
        with self._lock:
            before_repos = self._repo_attrs()
            before = {name: dict(repo._data) for name, repo in before_repos.items()}
            before_tenants = {name: dict(repo._tenant_by_id) for name, repo in before_repos.items()}
            processed_before = dict(self._processed)
            self._conn.execute("BEGIN")
            try:
                if self._remote:
                    self._reload(clear=True)
                result = super().transaction(fn)
                self._persist_changes(before, processed_before, commit=False)
                self._conn.commit()
                return result
            except Exception:
                try:
                    self._conn.rollback()
                finally:
                    for name, repo in self._repo_attrs().items():
                        repo._data = dict(before.get(name, {}))
                        repo._tenant_by_id = dict(before_tenants.get(name, {}))
                    self._processed = dict(processed_before)
                raise

    def _persist_changes(self, before: dict, processed_before: dict, commit: bool = True):
        cur = self._conn.cursor()
        for name, repo in self._repo_attrs().items():
            old = before.get(name, {})
            for record_id, value in repo._data.items():
                if record_id not in old or old[record_id] is not value:
                    cur.execute(
                        "INSERT OR REPLACE INTO records (repo, record_id, payload, tenant_id) VALUES (?, ?, ?, ?)",
                        (name, record_id, json.dumps(serialize_value(value)), repo.tenant_of(record_id) or "legacy"),
                    )
        for name, old_repo in before.items():
            current_repo = self._repo_attrs().get(name)
            if current_repo is None:
                continue
            for record_id in set(old_repo) - set(current_repo._data):
                cur.execute("DELETE FROM records WHERE repo = ? AND record_id = ?", (name, record_id))
        for command_id, value in self._processed.items():
            if command_id not in processed_before or processed_before[command_id] is not value:
                cur.execute(
                    "INSERT OR REPLACE INTO records (repo, record_id, payload, tenant_id) VALUES (?, ?, ?, ?)",
                    ("_processed", command_id, json.dumps(serialize_value(value)), command_id.split(":", 1)[0] if ":" in command_id else "legacy"),
                )
        for command_id in set(processed_before) - set(self._processed):
            cur.execute("DELETE FROM records WHERE repo = ? AND record_id = ?", ("_processed", command_id))
        if commit:
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
