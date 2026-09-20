from decimal import Decimal
from backend.functions.validators.money import money, require_non_negative

DEFAULT_RATE = Decimal("0.01")

def calculate_commission(amount: Decimal, rate: Decimal = DEFAULT_RATE, override: Decimal | None = None) -> Decimal:
    amount = require_non_negative(amount, "amount")
    if override is not None:
        return require_non_negative(override, "commission")
    return money(amount * rate)
