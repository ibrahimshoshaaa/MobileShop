#!/usr/bin/env python3
"""Authenticated client-level staging E2E gate.

This exercises the same standard-library HTTP client used by the desktop POS
against the deployed staging API. It deliberately uses only the read/sync
permissions provisioned for the isolated staging principal, so the test is
safe to repeat without mutating business data.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import quote

from apps.desktop.api_client import ApiClient, ApiError


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    base_url = required("STAGING_API_URL")
    token = required("STAGING_BEARER_TOKEN")
    branch = required("STAGING_BRANCH_ID")

    client = ApiClient(base_url=base_url, token=token, branch_id=branch, timeout=60)

    # Real desktop client path: authenticated product retrieval.
    products = client.get_products()
    assert isinstance(products, list), "desktop client did not decode products list"
    assert any(p.get("id") == "staging-product-1" for p in products), (
        "staging product is missing from the real client response"
    )

    # Exercise the same client HTTP machinery against the authenticated
    # operational query endpoint. This remains non-mutating.
    import urllib.request
    import json

    url = f"{base_url.rstrip('/')}/query/products?branch_id={quote(branch)}&limit=5"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert payload.get("ok") is True, f"query/products failed: {payload}"
    assert isinstance(payload.get("data"), list), "query/products data is not a list"

    # Authenticated empty sync upload is the client's safe sync handshake.
    sync_url = f"{base_url.rstrip('/')}/sync/upload"
    sync_body = json.dumps({"branch_id": branch, "commands": []}).encode()
    sync_req = urllib.request.Request(sync_url, data=sync_body, method="POST")
    sync_req.add_header("Authorization", f"Bearer {token}")
    sync_req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(sync_req, timeout=60) as response:
        sync_payload = json.loads(response.read().decode("utf-8"))
    assert sync_payload.get("ok") is True, f"sync/upload failed: {sync_payload}"

    print("CLIENT_E2E_OK")
    print("desktop_api_client=PASS")
    print("authenticated_product_read=PASS")
    print("authenticated_query=PASS")
    print("authenticated_sync_handshake=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
