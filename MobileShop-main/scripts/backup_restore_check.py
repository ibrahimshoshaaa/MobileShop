#!/usr/bin/env python3
"""Portable SQLite backup/restore drill.

This verifies that a durable database can be copied, restored into a clean
database, and passes SQLite integrity checks. In production, the same logical
drill must be executed against the managed Turso database/backup facility.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def backup_restore(source: Path, backup: Path, restored: Path) -> dict:
    if not source.exists():
        raise FileNotFoundError(source)
    for path in (backup, restored):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()

    src = sqlite3.connect(source)
    dst = sqlite3.connect(backup)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    check = sqlite3.connect(backup)
    integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
    check.close()
    if integrity != "ok":
        raise RuntimeError(f"backup integrity check failed: {integrity}")

    restored_db = sqlite3.connect(restored)
    backup_db = sqlite3.connect(backup)
    with restored_db:
        backup_db.backup(restored_db)
    backup_db.close()
    restored_integrity = restored_db.execute("PRAGMA integrity_check").fetchone()[0]
    restored_db.close()
    if restored_integrity != "ok":
        raise RuntimeError(f"restore integrity check failed: {restored_integrity}")

    return {"backup": str(backup), "restored": str(restored), "integrity": "ok"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("backup", type=Path)
    parser.add_argument("restored", type=Path)
    args = parser.parse_args()
    print(backup_restore(args.source, args.backup, args.restored))
