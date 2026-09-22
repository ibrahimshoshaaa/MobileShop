"""Vercel serverless entrypoint for the Mobile Shop ERP API.

Production configuration is supplied by Vercel environment variables:
APP_ENV=production
AUTH_PROVIDER=firebase
TURSO_DATABASE_URL
TURSO_AUTH_TOKEN
Firebase Admin credentials must be available through the standard
firebase-admin runtime configuration.
"""
from backend.api_server.main import app

__all__ = ["app"]
