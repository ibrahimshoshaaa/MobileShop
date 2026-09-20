from backend.functions.offline.protocol import SyncProtocol
from shared.contracts.errors import DomainError


def test_upload_is_idempotent_and_cursored(tmp_path):
    sync = SyncProtocol(tmp_path / "sync.db")
    calls = []
    def execute(envelope):
        calls.append(envelope["command_id"])
        return {"ok": True, "id": envelope["command_id"]}

    envelope = {"command_id": "c1", "tenant_id": "t1", "branch_id": "b1", "payload": {"x": 1}}
    first = sync.upload([envelope], tenant_id="t1", branch_id="b1", executor=execute)
    second = sync.upload([envelope], tenant_id="t1", branch_id="b1", executor=execute)
    assert first["results"][0]["status"] == "APPLIED"
    assert second["results"][0]["idempotent_replay"] is True
    assert calls == ["c1"]
    page = sync.download(tenant_id="t1", branch_id="b1")
    assert page["next_cursor"] == 1
    assert len(page["changes"]) == 1
    sync.close()


def test_upload_rejects_cross_tenant_envelope_without_execution(tmp_path):
    sync = SyncProtocol(tmp_path / "sync.db")
    called = []
    out = sync.upload(
        [{"command_id": "c1", "tenant_id": "other", "branch_id": "b1"}],
        tenant_id="t1", branch_id="b1", executor=lambda x: called.append(x),
    )
    assert out["results"][0]["status"] == "CONFLICT"
    assert called == []
    sync.close()


def test_stale_version_is_a_conflict(tmp_path):
    sync = SyncProtocol(tmp_path / "sync.db")
    class Conflict(DomainError):
        pass
    def execute(_):
        raise DomainError("STALE_VERSION", "stale", {})
    out = sync.upload(
        [{"command_id": "c1", "tenant_id": "t1", "branch_id": "b1"}],
        tenant_id="t1", branch_id="b1", executor=execute,
    )
    assert out["results"][0]["status"] == "CONFLICT"
    assert out["results"][0]["error_code"] == "STALE_VERSION"
    sync.close()
