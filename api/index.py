"""Vercel serverless entrypoint for the Mobile Shop ERP API.

Production configuration is supplied by Vercel environment variables:
APP_ENV=production
AUTH_PROVIDER=turso
AUTH_JWT_SECRET
TURSO_DATABASE_URL
TURSO_AUTH_TOKEN
"""
from backend.api_server.main import app

__all__ = ["app"]
