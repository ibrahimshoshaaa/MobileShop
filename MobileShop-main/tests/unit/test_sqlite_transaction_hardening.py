import pytest
from backend.functions.persistence.sqlite_repository import SQLiteRepository

def test_transaction_rolls_back(tmp_path):
    repo = SQLiteRepository(tmp_path / "erp.db")
    with pytest.raises(RuntimeError):
        with repo.transaction() as db:
            db.execute("INSERT INTO commands(command_id,tenant_id,branch_id,command,payload) VALUES(?,?,?,?,?)",
                       ("x", "t", "b", "sale", "{}"))
            raise RuntimeError("boom")
    assert repo.conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 0

def test_command_id_cannot_cross_tenant(tmp_path):
    repo = SQLiteRepository(tmp_path / "erp.db")
    repo.submit_command(command_id="x", tenant_id="t1", branch_id="b1", command="sale", payload={})
    with pytest.raises(ValueError):
        repo.submit_command(command_id="x", tenant_id="t2", branch_id="b2", command="sale", payload={})

def test_pending_can_be_scoped_to_branch(tmp_path):
    repo = SQLiteRepository(tmp_path / "erp.db")
    repo.submit_command(command_id="x", tenant_id="t", branch_id="b1", command="sale", payload={})
    repo.submit_command(command_id="y", tenant_id="t", branch_id="b2", command="sale", payload={})
    rows = repo.pending_commands("t", branch_id="b1")
    assert [r["command_id"] for r in rows] == ["x"]
