import pytest
from shared.contracts.errors import DomainError
from backend.functions.validators.permissions import require_permission

def test_missing_permission_is_rejected():
    with pytest.raises(DomainError) as exc:
        require_permission(frozenset(), "wallet.transfer")
    assert exc.value.code == "FORBIDDEN"
