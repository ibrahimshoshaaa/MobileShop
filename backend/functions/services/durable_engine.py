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
    def __init__(self, db_path: str | Path = "erp_durable.db"):
        super().__init__()
        self._db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                repo TEXT NOT NULL,
                record_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (repo, record_id)
            )
            """
        )
        self._conn.commit()
        self._reload()

    def _repo_attrs(self) -> dict:
        return {name: value for name, value in self.__dict__.items() if hasattr(value, "_data")}

    def _reload(self) -> None:
        cur = self._conn.execute("SELECT repo, record_id, payload FROM records")
        for repo_name, record_id, payload in cur.fetchall():
            value = deserialize_value(json.loads(payload))
            if repo_name == "_processed":
                self._processed[record_id] = value
                continue
            repo = getattr(self, repo_name, None)
            if repo is not None and hasattr(repo, "_data"):
                repo._data[record_id] = value

    def transaction(self, fn):
        with self._lock:
            before_repos = self._repo_attrs()
            before = {name: dict(repo._data) for name, repo in before_repos.items()}
            processed_before = dict(self._processed)
            result = super().transaction(fn)
            # Only reached on success — on exception, super().transaction()
            # already rolled the in-memory state back and re-raised, so
            # there's nothing new here to persist.
            self._persist_changes(before, processed_before)
            return result

    def _persist_changes(self, before: dict, processed_before: dict) -> None:
        cur = self._conn.cursor()
        for name, repo in self._repo_attrs().items():
            old = before.get(name, {})
            for record_id, value in repo._data.items():
                if record_id not in old or old[record_id] is not value:
                    cur.execute(
                        "INSERT OR REPLACE INTO records (repo, record_id, payload) VALUES (?, ?, ?)",
                        (name, record_id, json.dumps(serialize_value(value))),
                    )
        for command_id, value in self._processed.items():
            if command_id not in processed_before or processed_before[command_id] is not value:
                cur.execute(
                    "INSERT OR REPLACE INTO records (repo, record_id, payload) VALUES (?, ?, ?)",
                    ("_processed", command_id, json.dumps(serialize_value(value))),
                )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
