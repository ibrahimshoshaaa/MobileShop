#!/usr/bin/env python3
"""Static production-readiness audit for the deployed API boundary."""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(f"PRODUCTION_AUDIT_FAIL: {message}")
    raise SystemExit(1)


main = read("backend/api_server/main.py")
vercel = read("vercel.json")
requirements = read("pyproject.toml")
workflow = read(".github/workflows/ci.yml")

checks = {
    "production_refuses_dev_auth": 'Refusing to start production with development-token authentication' in main,
    "production_requires_firebase": 'Production requires AUTH_PROVIDER=firebase' in main,
    "production_requires_turso_url": 'Production requires TURSO_DATABASE_URL and TURSO_AUTH_TOKEN' in main,
    "vercel_python_entrypoint": '"src": "api/index.py"' in vercel and '"use": "@vercel/python"' in vercel,
    "fastapi_declared": '"fastapi>=' in requirements,
    "firebase_declared": '"firebase-admin>=' in requirements,
    "libsql_declared": '"libsql==' in requirements,
    "security_ci_present": "bandit" in workflow and "pip-audit" in workflow,
}

for name, ok in checks.items():
    if not ok:
        fail(name)
    print(f"{name}=PASS")

# Catch accidental credential material in tracked source files commonly used
# by this project. Real runtime secrets must arrive through the deployment
# environment, never through source control.
for relative in ("backend", "scripts", ".github"):
    for path in (ROOT / relative).rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".yml", ".yaml", ".toml", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"AIza[0-9A-Za-z_-]{20,}", text):
            fail(f"possible Firebase API key committed in {path.relative_to(ROOT)}")
        if re.search(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", text):
            fail(f"private key material committed in {path.relative_to(ROOT)}")

print("PRODUCTION_AUDIT_OK")
