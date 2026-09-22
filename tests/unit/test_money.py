from decimal import Decimal
import pytest
from shared.contracts.errors import DomainError
from backend.functions.validators.money import money, require_non_negative

def test_money_rounding():
    assert money(Decimal("1.005")) == Decimal("1.01")

def test_negative_rejected():
    with pytest.raises(DomainError):
        require_non_negative(Decimal("-1"), "amount")
