#!/usr/bin/env python3
"""Staging smoke test for the deployed API.

Required environment:
  STAGING_API_URL
  STAGING_BEARER_TOKEN
  STAGING_BRANCH_ID
"""
from __future__ import annotations

import base64
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(url: str, token: str, method: str = "GET", body: dict | None = None):
    payload = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=payload, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urlopen(req, timeout=15) as response:
        return response.status, json.loads(response.read().decode())



def _token_metadata(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return {"aud": claims.get("aud"), "iss": claims.get("iss"), "tenant_id": claims.get("tenant_id"), "branch_ids": claims.get("branch_ids"), "permissions": claims.get("permissions")}
    except Exception:
        return {}


def _request_checked(url: str, token: str, label: str, method: str = "GET", body: dict | None = None):
    try:
        return request(url, token, method, body)
    except HTTPError as exc:
        print(f"staging smoke: {label} -> HTTP {exc.code}", file=sys.stderr)
        raise

def main() -> int:
    required = ("STAGING_API_URL", "STAGING_BEARER_TOKEN", "STAGING_BRANCH_ID")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError("missing required staging configuration: " + ", ".join(missing))
    base = os.environ["STAGING_API_URL"].strip().rstrip("/")
    token = os.environ["STAGING_BEARER_TOKEN"].strip()
    branch = os.environ["STAGING_BRANCH_ID"].strip()
    if not base.startswith(("https://", "http://")):
        raise RuntimeError("STAGING_API_URL must start with http:// or https://")
    print("staging token metadata:", json.dumps(_token_metadata(token), sort_keys=True))
    status, health = _request_checked(f"{base}/health", token, "health")
    if status != 200 or health.get("status") != "ok":
        raise RuntimeError(f"health check failed: {status} {health}")
    status, products = _request_checked(f"{base}/products?branch_id={branch}", token, "products")
    if status != 200 or products.get("ok") is not True:
        raise RuntimeError(f"products query failed: {status} {products}")
    status, query = _request_checked(f"{base}/query/products?branch_id={branch}&limit=5", token, "query/products")
    if status != 200 or query.get("ok") is not True:
        raise RuntimeError(f"query endpoint failed: {status} {query}")
    status, changes = _request_checked(f"{base}/sync/changes?branch_id={branch}&cursor=0&limit=5", token, "sync/changes")
    if status != 200 or changes.get("ok") is not True:
        raise RuntimeError(f"sync changes failed: {status} {changes}")
    status, upload = _request_checked(f"{base}/sync/upload", token, "sync/upload", "POST", {"branch_id": branch, "commands": []})
    if status != 200 or upload.get("ok") is not True:
        raise RuntimeError(f"sync upload failed: {status} {upload}")
    print("staging smoke: PASS (health/products/query/sync)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, HTTPError, URLError, TimeoutError, RuntimeError) as exc:
        print(f"staging smoke: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
