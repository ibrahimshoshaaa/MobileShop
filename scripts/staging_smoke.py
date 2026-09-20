#!/usr/bin/env python3
"""Staging smoke test for the deployed API.

Required environment:
  STAGING_API_URL
  STAGING_BEARER_TOKEN
  STAGING_BRANCH_ID
"""
from __future__ import annotations

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


def main() -> int:
    base = os.environ["STAGING_API_URL"].rstrip("/")
    token = os.environ["STAGING_BEARER_TOKEN"]
    branch = os.environ["STAGING_BRANCH_ID"]
    status, health = request(f"{base}/health", token)
    if status != 200 or health.get("status") != "ok":
        raise RuntimeError(f"health check failed: {status} {health}")
    status, products = request(f"{base}/products?branch_id={branch}", token)
    if status != 200 or products.get("ok") is not True:
        raise RuntimeError(f"products query failed: {status} {products}")
    print("staging smoke: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, HTTPError, URLError, TimeoutError, RuntimeError) as exc:
        print(f"staging smoke: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
