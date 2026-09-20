from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

@dataclass(frozen=True)
class CommandContext:
    command_id: str
    user_id: str
    branch_id: str
    permissions: frozenset[str] = frozenset()

@dataclass(frozen=True)
class TransferCommand:
    context: CommandContext
    source_wallet_id: str
    destination_wallet_id: str
    amount: Decimal
    commission: Decimal | None = None
    reference: str | None = None

@dataclass(frozen=True)
class CreateSaleCommand:
    context: CommandContext
    customer_id: str | None
    items: tuple[dict[str, Any], ...]
    payments: tuple[dict[str, Any], ...]
    discount: Decimal = Decimal("0")

@dataclass(frozen=True)
class CollectInstallmentCommand:
    context: CommandContext
    installment_id: str
    amount: Decimal
    wallet_id: str
