"""HTTP client for the real backend API server (backend/api_server), used by
*_repo modules when running in 'online' mode instead of local SQLite. Uses
only the standard library (urllib) so the desktop app doesn't need any pip
dependency to talk to the API — the dependency (fastapi/uvicorn) is only
needed to *run* the server, not to be a client of it.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

try:
    # Package import path (CI/tests).
    from .errors import AppError
except ImportError:
    # Script/legacy launch path (running from apps/desktop).
    from errors import AppError

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TOKEN = "dev-owner-token"
DEFAULT_BRANCH_ID = "LOCAL_BRANCH"


class ApiError(AppError):
    """Same shape as AppError so the existing Tkinter error-label pattern
    works unchanged whether the app is in offline or online mode."""


class ApiClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, token: str = DEFAULT_TOKEN, branch_id: str = DEFAULT_BRANCH_ID):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.branch_id = branch_id

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode("utf-8"))
            except Exception:
                payload = {}
            message = (payload.get("error") or {}).get("message") or f"خطأ من السيرفر (كود {e.code})."
            raise ApiError(message) from e
        except urllib.error.URLError as e:
            raise ApiError(f"تعذّر الاتصال بالسيرفر على {self.base_url}: {e.reason}") from e

    def command(self, command_id: str, command: str, payload: dict):
        result = self._request(
            "POST", "/command",
            {"commandId": command_id, "command": command, "branchId": self.branch_id, "payload": payload},
        )
        if not result.get("ok", True):
            raise ApiError((result.get("error") or {}).get("message", "فشلت العملية."))
        return result.get("data")

    def get_products(self):
        return self.get_entity("products")

    def get_entity(self, entity: str, limit: int = 100):
        result = self._request("GET", f"/query/{entity}?branch_id={self.branch_id}&limit={limit}")
        if not result.get("ok", True):
            raise ApiError((result.get("error") or {}).get("message", "تعذّر تحميل البيانات."))
        return result.get("data", [])

    def get_sales(self, limit: int = 50):
        result = self._request("GET", f"/sales?branch_id={self.branch_id}&limit={limit}")
        if not result.get("ok", True):
            raise ApiError((result.get("error") or {}).get("message", "تعذّر تحميل المبيعات."))
        return result.get("data", [])

    def get_customers(self, limit: int = 100):
        return self.get_entity("customers", limit)

    def get_wallets(self, limit: int = 100):
        return self.get_entity("wallets", limit)
