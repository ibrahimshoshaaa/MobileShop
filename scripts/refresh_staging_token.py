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
from google.oauth2 import service_account


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    raw = required("FIREBASE_SERVICE_ACCOUNT_JSON")
    uid = required("FIREBASE_STAGING_UID")

    if not firebase_admin._apps:
        firebase_service_account_data = json.loads(raw)
        firebase_admin.initialize_app(credentials.Certificate(firebase_service_account_data))

    app = firebase_admin.get_app()
    service_account_data = json.loads(raw)
    google_cred = service_account.Credentials.from_service_account_info(
        service_account_data,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    google_cred.refresh(Request())

    project_id = getattr(google_cred, "project_id", None) or app.project_id
    if not project_id:
        raise SystemExit("Could not determine Firebase project ID")

    # The authenticated Identity Toolkit v1 config endpoint returns the Web API
    # key for a developer/service-account call. This avoids storing a separate
    # Firebase Web API key as a GitHub secret.
    project_url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}"
    project_request = urllib.request.Request(
        project_url,
        headers={"Authorization": f"Bearer {google_cred.token}"},
    )
    with urllib.request.urlopen(project_request, timeout=20) as response:
        project = json.loads(response.read().decode("utf-8"))
    project_number = str(project.get("projectNumber") or "").strip()
    if not project_number:
        raise SystemExit("Could not determine Firebase project number")

    config_url = (
        "https://identitytoolkit.googleapis.com/v1/projects"
        f"?projectNumber={project_number}"
    )
    request = urllib.request.Request(
        config_url,
        headers={"Authorization": f"Bearer {google_cred.token}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        config = json.loads(response.read().decode("utf-8"))

    api_key = str(config.get("apiKey") or "").strip()

    custom_token = auth.create_custom_token(uid, app=app)
    if isinstance(custom_token, bytes):
        custom_token = custom_token.decode("utf-8")

    exchange_url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
    payload = json.dumps({
        "token": custom_token,
        "returnSecureToken": True,
    }).encode("utf-8")
    exchange_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {google_cred.token}",
    }
    if api_key:
        exchange_url += f"?key={api_key}"
    exchange_request = urllib.request.Request(
        exchange_url,
        data=payload,
        method="POST",
        headers=exchange_headers,
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
