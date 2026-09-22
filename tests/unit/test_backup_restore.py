import sqlite3
from pathlib import Path

from scripts.backup_restore_check import backup_restore


def test_backup_restore_drill(tmp_path: Path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    restored = tmp_path / "restored.db"
    db = sqlite3.connect(source)
    db.execute("CREATE TABLE records(id TEXT PRIMARY KEY, value TEXT)")
    db.execute("INSERT INTO records VALUES('r1','ok')")
    db.commit()
    db.close()

    result = backup_restore(source, backup, restored)
    assert result["integrity"] == "ok"
    db = sqlite3.connect(restored)
    assert db.execute("SELECT value FROM records WHERE id='r1'").fetchone()[0] == "ok"
    db.close()
