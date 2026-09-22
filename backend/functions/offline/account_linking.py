"""Offline-first account linking contract.

The local app may run without an account. When the owner enables cloud mode,
credentials are exchanged with the server; plaintext passwords are never
stored in the local database or in application tables.
"""
from dataclasses import dataclass
from enum import Enum


class SyncMode(str, Enum):
    OFFLINE = "offline"
    ONLINE = "online"


@dataclass(frozen=True)
class LinkedAccount:
    account_id: str
    email: str
    tenant_id: str
    branch_ids: tuple[str, ...]
    sync_mode: SyncMode = SyncMode.ONLINE


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not value or "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("invalid email")
    return value


def build_account_link_request(email: str, password: str) -> dict[str, str]:
    """Build a transient login request; callers must not persist password."""
    if not password or len(password) < 8:
        raise ValueError("password must contain at least 8 characters")
    return {"email": normalize_email(email), "password": password}
