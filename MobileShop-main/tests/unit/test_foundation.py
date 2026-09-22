from decimal import Decimal
import pytest
from shared.models.foundation import Branch, User, Settings
from backend.functions.repositories.foundation import InMemoryRepository
from backend.functions.branches.service import BranchService
from backend.functions.auth.authorization import authorize_branch, effective_permissions
from backend.functions.settings.service import SettingsService
from shared.contracts.errors import DomainError


def test_branch_creation_and_duplicate_code():
    repo = InMemoryRepository(); svc = BranchService(repo)
    svc.create(Branch(id="b1", name="Main", code="MAIN"))
    with pytest.raises(ValueError, match="DUPLICATE_BRANCH_CODE"):
        svc.create(Branch(id="b2", name="Second", code="MAIN"))


def test_branch_authorization():
    user = User(id="u1", name="Owner", branch_ids=("b1",))
    authorize_branch(user, "b1")
    with pytest.raises(DomainError) as e:
        authorize_branch(user, "b2")
    assert e.value.code == "BRANCH_ACCESS_DENIED"


def test_effective_permissions():
    user = User(id="u1", name="x", role_ids=("CASHIER",), permissions_override=("reports.view",))
    perms = effective_permissions(user, {"CASHIER": {"sales.create"}})
    assert perms == frozenset({"sales.create", "reports.view"})


def test_settings_currency_and_rate():
    svc = SettingsService()
    assert svc.validate(Settings()).currency == "EGP"
    with pytest.raises(ValueError, match="INVALID_INPUT"):
        svc.validate(Settings(default_transfer_commission_rate=Decimal("1.1")))
    with pytest.raises(ValueError, match="INVALID_CURRENCY"):
        svc.validate(Settings(currency="USD"))
