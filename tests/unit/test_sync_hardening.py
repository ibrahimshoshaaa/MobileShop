import pytest
from backend.functions.offline.local_store import LocalStore
from backend.functions.offline.sync import OfflineSync

def test_sync_rejects_wrong_tenant_before_executor():
    store = LocalStore()
    store.link_account(account_id="a", email="x@y.com", tenant_id="tenant-a", branch_ids=["b1"])
    store.enqueue("c1", {"_tenant_id":"tenant-b", "_branch_id":"b1"})
    called=[]
    result = OfflineSync(store=store).sync(lambda p: called.append(p))
    assert result.conflicts == ["c1"]
    assert called == []
    assert store.pending() == []

def test_sync_rejects_unassigned_branch_before_executor():
    store = LocalStore()
    store.link_account(account_id="a", email="x@y.com", tenant_id="tenant-a", branch_ids=["b1"])
    store.enqueue("c1", {"_tenant_id":"tenant-a", "_branch_id":"b2"})
    result = OfflineSync(store=store).sync(lambda p: None)
    assert result.conflicts == ["c1"]

def test_sync_classifies_stale_version_as_conflict():
    store = LocalStore()
    store.link_account(account_id="a", email="x@y.com", tenant_id="tenant-a", branch_ids=["b1"])
    store.enqueue("c1", {"_tenant_id":"tenant-a", "_branch_id":"b1"})
    class E(Exception):
        code = "STALE_VERSION"
    result = OfflineSync(store=store).sync(lambda p: (_ for _ in ()).throw(E()))
    assert result.conflicts == ["c1"]
