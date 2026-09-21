import pytest
from shared.contracts.commands import CommandContext
from shared.contracts.errors import DomainError
from shared.models.erp import Branch, ERPUser, ERPUserRole
from backend.functions.services.erp_engine import ERPCommandEngine
from backend.functions.repositories.generic import reset_tenant_scope, set_tenant_scope

def ctx(cid, perms, branch="b1", tenant="tenant-a"):
    return CommandContext(cid, "admin", branch, frozenset(perms), tenant)

def test_branch_role_user_access_lifecycle():
    e = ERPCommandEngine()
    e.create_branch(ctx("b", {"branches.manage"}), Branch("b1", "Main", "MAIN"))
    e.create_branch(ctx("b2", {"branches.manage"}), Branch("b2", "Second", "SECOND"))
    e.create_role(ctx("r", {"roles.manage"}), ERPUserRole("manager", "Manager", ("sales.create", "inventory.read")))
    user = e.create_user_profile(ctx("u", {"users.manage"}), ERPUser("u1", "Cashier", ("b1",), "manager"))
    assert user.role_id == "manager"
    assert user.branch_ids == ("b1",)
    updated = e.update_user_access(ctx("ua", {"users.manage"}), "u1", ("b1", "b2"), "manager", ("customers.read",))
    assert updated.branch_ids == ("b1", "b2")
    assert updated.permissions == ("customers.read",)

def test_user_cannot_be_assigned_unknown_or_inactive_branch():
    e = ERPCommandEngine()
    e.create_branch(ctx("b", {"branches.manage"}), Branch("b1", "Main", "MAIN"))
    with pytest.raises(DomainError) as exc:
        e.create_user_profile(ctx("u", {"users.manage"}), ERPUser("u1", "User", ("missing",)))
    assert exc.value.code == "NOT_FOUND"

def test_branch_and_user_queries_are_tenant_scoped():
    e = ERPCommandEngine()
    e.create_branch(ctx("a", {"branches.manage"}, tenant="tenant-a"), Branch("a1", "A", "A"))
    e.create_branch(ctx("b", {"branches.manage"}, tenant="tenant-b"), Branch("b1", "B", "B"))
    assert [b.id for b in e.branches.all()] == ["a1"]
    token = set_tenant_scope("tenant-b")
    try:
        assert [b.id for b in e.branches.all()] == ["b1"]
    finally:
        reset_tenant_scope(token)
