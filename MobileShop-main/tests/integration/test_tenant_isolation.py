from backend.functions.repositories.generic import Repository, set_tenant_scope, reset_tenant_scope

def test_repository_hides_cross_tenant_records():
    repo = Repository()
    token = set_tenant_scope("tenant-a")
    try:
        repo.create("customer-1", {"tenant_id": "tenant-a"})
    finally:
        reset_tenant_scope(token)
    token = set_tenant_scope("tenant-b")
    try:
        assert repo.get("customer-1") is None
        assert repo.all() == []
    finally:
        reset_tenant_scope(token)

def test_repository_blocks_cross_tenant_mutation():
    import pytest
    repo = Repository()
    token = set_tenant_scope("tenant-a")
    try:
        repo.create("x", {"value": 1})
    finally:
        reset_tenant_scope(token)
    token = set_tenant_scope("tenant-b")
    try:
        with pytest.raises(KeyError):
            repo.update("x", {"value": 2})
        with pytest.raises(KeyError):
            repo.delete("x")
    finally:
        reset_tenant_scope(token)
