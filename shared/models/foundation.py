from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

@dataclass(frozen=True)
class User:
    id: str
    name: str
    phone: str | None = None
    email: str | None = None
    role_ids: tuple[str, ...] = ()
    branch_ids: tuple[str, ...] = ()
    permissions_override: tuple[str, ...] = ()
    status: str = "ACTIVE"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    last_login_at: datetime | None = None

@dataclass(frozen=True)
class Branch:
    id: str
    name: str
    code: str
    address: str | None = None
    phone: str | None = None
    status: str = "ACTIVE"
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

@dataclass(frozen=True)
class Settings:
    currency: str = "EGP"
    default_transfer_commission_rate: Any = 0.01
    installment_rate_table: dict[str, Any] = field(default_factory=dict)
    warranty: dict[str, Any] = field(default_factory=dict)
    return_policy: dict[str, Any] = field(default_factory=dict)
    exchange_policy: dict[str, Any] = field(default_factory=dict)
    discount_permissions: tuple[str, ...] = ()
    invoice: dict[str, Any] = field(default_factory=dict)
    numbering: dict[str, Any] = field(default_factory=dict)
    employee_commission_rules: dict[str, Any] = field(default_factory=dict)
    allowed_wallets: tuple[str, ...] = ()
    tax: dict[str, Any] = field(default_factory=dict)
