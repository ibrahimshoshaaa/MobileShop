#!/usr/bin/env python3
"""Mint a fresh Firebase ID token for the isolated staging principal.

The repository used to keep a long-lived ID token in STAGING_BEARER_TOKEN.
Firebase ID tokens expire after about one hour, so the staging gates must mint
one for each run instead of reusing a stale token.
"""
from __future__ import annotations

import json
import os
import urllib.request

import firebase_admin
from firebase_admin import auth, credentials
from google.auth.transport.requests import Request


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    raw = required("FIREBASE_SERVICE_ACCOUNT_JSON")
    uid = required("FIREBASE_STAGING_UID")

    if not firebase_admin._apps:
        service_account = json.loads(raw)
        firebase_admin.initialize_app(credentials.Certificate(service_account))

    app = firebase_admin.get_app()
    google_cred = app.credential.get_credential()
    if not google_cred.valid:
        google_cred.refresh(Request())

    project_id = getattr(google_cred, "project_id", None) or app.project_id
    if not project_id:
        raise SystemExit("Could not determine Firebase project ID")

    config_url = f"https://identitytoolkit.googleapis.com/v2/projects/{project_id}/config"
    request = urllib.request.Request(
        config_url,
        headers={"Authorization": f"Bearer {google_cred.token}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        config = json.loads(response.read().decode("utf-8"))

    api_key = ((config.get("clientConfig") or {}).get("apiKey") or "").strip()
    if not api_key:
        raise SystemExit("Firebase Identity Platform API key was not returned by project config")

    custom_token = auth.create_custom_token(uid, app=app)
    if isinstance(custom_token, bytes):
        custom_token = custom_token.decode("utf-8")

    exchange_url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
        f"?key={api_key}"
    )
    payload = json.dumps({
        "token": custom_token,
        "returnSecureToken": True,
    }).encode("utf-8")
    exchange_request = urllib.request.Request(
        exchange_url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(exchange_request, timeout=20) as response:
        result = json.loads(response.read().decode("utf-8"))

    token = result.get("idToken")
    if not token:
        raise SystemExit("Firebase did not return an ID token")

    print(f"::add-mask::{token}")
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env_file:
        env_file.write(f"STAGING_BEARER_TOKEN={token}\n")

    print("Fresh staging Firebase ID token minted successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
