import pytest
from backend.functions.offline.account_linking import (
    SyncMode, build_account_link_request, normalize_email, LinkedAccount,
)


def test_email_is_normalized():
    assert normalize_email("  Owner@Example.COM ") == "owner@example.com"


def test_login_request_does_not_create_persistent_password_field():
    request = build_account_link_request("Owner@Example.com", "strong-pass")
    assert request == {"email": "owner@example.com", "password": "strong-pass"}
    assert "password_hash" not in request


def test_short_password_rejected():
    with pytest.raises(ValueError):
        build_account_link_request("owner@example.com", "short")


def test_linked_account_has_cloud_identity_and_branches():
    account = LinkedAccount("acct-1", "owner@example.com", "tenant-1", ("b1", "b2"))
    assert account.sync_mode is SyncMode.ONLINE
    assert account.branch_ids == ("b1", "b2")

from backend.functions.offline.local_store import LocalStore
from backend.functions.offline.sync import OfflineSync


def test_local_store_never_creates_password_column():
    store = LocalStore()
    store.set_mode("offline")
    store.link_account(account_id="a1", email=" OWNER@EXAMPLE.COM ", tenant_id="t1", branch_ids=["b2", "b1"])
    profile = store.profile()
    assert profile["email"] == "owner@example.com"
    assert profile["branch_ids"] == ["b1", "b2"]
    columns = [row[1] for row in store.db.execute("PRAGMA table_info(device_profile)")]
    assert "password" not in columns and "password_hash" not in columns


def test_persistent_sync_queue_is_idempotent():
    store = LocalStore()
    sync = OfflineSync(store=store)
    sync.enqueue("cmd-1", {"command": "createSale"})
    sync.enqueue("cmd-1", {"command": "tampered"})
    assert len(store.pending()) == 1
    result = sync.sync(lambda payload: None)
    assert result.applied == ["cmd-1"]
    assert store.pending() == []


def test_local_store_scoped_queue_and_unlink():
    from backend.functions.offline.local_store import LocalStore
    store = LocalStore()
    store.link_account(account_id='a1', email='Owner@Example.com', tenant_id='t1', branch_ids=['b1'])
    store.enqueue_scoped('cmd-1', 't1', 'b1', {'command': 'createSale'})
    assert store.pending()[0]['payload']['_tenant_id'] == 't1'
    try:
        store.enqueue_scoped('cmd-2', 't2', 'b1', {'command': 'createSale'})
        assert False
    except ValueError:
        pass
    store.clear_account()
    assert store.profile()['sync_mode'] == 'offline'
    assert store.profile()['tenant_id'] is None
