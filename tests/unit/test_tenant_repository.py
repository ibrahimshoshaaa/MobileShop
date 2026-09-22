import pytest
from backend.functions.repositories.generic import Repository, set_tenant_scope, reset_tenant_scope


def test_legacy_records_are_not_visible_in_production(monkeypatch):
    repo = Repository()
    repo.create("legacy", {"id": "legacy"})
    monkeypatch.setenv("APP_ENV", "production")
    token = set_tenant_scope("tenant-a")
    try:
        assert repo.get("legacy") is None
    finally:
        reset_tenant_scope(token)
