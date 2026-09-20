from __future__ import annotations

from contextvars import ContextVar
from threading import RLock

_CURRENT_TENANT: ContextVar[str | None] = ContextVar("erp_current_tenant", default=None)

def set_tenant_scope(tenant_id: str | None):
    if tenant_id is not None and (not isinstance(tenant_id, str) or not tenant_id.strip()):
        raise ValueError("tenant_id must be a non-empty string")
    return _CURRENT_TENANT.set(tenant_id)

def reset_tenant_scope(token) -> None:
    _CURRENT_TENANT.reset(token)

def current_tenant() -> str | None:
    return _CURRENT_TENANT.get()

class Repository:
    """Tenant-aware repository with request-scope filtering."""
    def __init__(self):
        self._data = {}
        self._tenant_by_id = {}
        self._lock = RLock()

    def _visible(self, record_id):
        scope = current_tenant()
        if scope is None:
            return True
        return self._tenant_by_id.get(record_id, "legacy") == scope

    def get(self, k):
        value = self._data.get(k)
        return value if value is not None and self._visible(k) else None

    def create(self, k, v):
        with self._lock:
            if k in self._data:
                raise ValueError("ALREADY_EXISTS")
            scope = current_tenant()
            self._data[k] = v
            self._tenant_by_id[k] = scope if scope is not None else "legacy"
            return v

    def update(self, k, v):
        with self._lock:
            if k not in self._data or not self._visible(k):
                raise KeyError("NOT_FOUND")
            self._data[k] = v
            return v

    def delete(self, k):
        with self._lock:
            if k not in self._data or not self._visible(k):
                raise KeyError("NOT_FOUND")
            del self._data[k]
            self._tenant_by_id.pop(k, None)

    def all(self):
        return [value for key, value in self._data.items() if self._visible(key)]

    def tenant_of(self, k):
        return self._tenant_by_id.get(k)

    def raw_all(self):
        return list(self._data.values())
