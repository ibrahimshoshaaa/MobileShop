from decimal import Decimal, ROUND_HALF_UP
from shared.contracts.errors import DomainError

CENT = Decimal("0.01")

def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)

def require_non_negative(value: Decimal, field: str) -> Decimal:
    value = money(value)
    if value < 0:
        raise DomainError("INVALID_INPUT", f"{field} لا يمكن أن يكون سالبًا.", {"field": field})
    return value
