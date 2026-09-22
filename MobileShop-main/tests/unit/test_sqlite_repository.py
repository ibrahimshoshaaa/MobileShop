import json
from backend.functions.persistence.sqlite_repository import SQLiteRepository

def test_sqlite_command_idempotency_and_tenant_scope(tmp_path):
    repo = SQLiteRepository(tmp_path / 'local.db')
    assert repo.submit_command(command_id='c1', tenant_id='t1', branch_id='b1', command='sale', payload={'total': 10}) == 'PENDING'
    assert repo.submit_command(command_id='c1', tenant_id='t1', branch_id='b1', command='sale', payload={'total': 999}) == 'PENDING'
    assert len(repo.pending_commands('t1')) == 1
    assert repo.pending_commands('t2') == []
    repo.mark_command('c1', 'APPLIED')
    assert repo.pending_commands('t1') == []
    repo.close()


def test_scoped_record_upsert_and_optimistic_version(tmp_path):
    from backend.functions.persistence.sqlite_repository import SQLiteRepository
    import pytest
    repo = SQLiteRepository(tmp_path / "records.db")
    assert repo.upsert_record(entity="product", record_id="p1", tenant_id="t1", branch_id="b1", payload={"qty": 2}) == 1
    assert repo.upsert_record(entity="product", record_id="p1", tenant_id="t1", branch_id="b1", payload={"qty": 3}, expected_version=1) == 2
    assert repo.get_record(entity="product", record_id="p1", tenant_id="t1", branch_id="b1")["version"] == 2
    with pytest.raises(ValueError, match="STALE_VERSION"):
        repo.upsert_record(entity="product", record_id="p1", tenant_id="t1", branch_id="b1", payload={"qty": 4}, expected_version=1)
    assert repo.get_record(entity="product", record_id="p1", tenant_id="t2", branch_id="b1") is None
    repo.close()
