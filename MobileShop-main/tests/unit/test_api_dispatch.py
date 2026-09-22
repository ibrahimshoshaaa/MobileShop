"""Covers backend/functions/api/dispatch.py — specifically createProduct,
createCustomer and createSupplier, which previously passed a raw dict where
create_product/create_customer/create_supplier expect a domain dataclass
(this was unexercised by any existing test; only createSale and
collectInstallment had contract-building logic before this fix).
"""
from shared.contracts.commands import CommandContext
from backend.functions.services.erp_engine import ERPCommandEngine
from backend.functions.api.dispatch import dispatch
from backend.functions.api.http import handle


def ctx(cid, perms=None, branch="b1"):
    perms = perms or {"products.edit", "customers.edit", "suppliers.edit"}
    return CommandContext(cid, "u", branch, frozenset(perms))


def test_dispatch_create_product_builds_dataclass():
    e = ERPCommandEngine()
    result = dispatch(e, "createProduct", ctx("p1"), product={
        "name": "شاحن", "sku": "SKU-1", "product_type": "ACCESSORY",
        "selling_price": "50", "default_cost": "20",
    })
    assert result.sku == "SKU-1"
    assert e.products.get("p1") is result


def test_dispatch_create_product_rejects_duplicate_sku():
    e = ERPCommandEngine()
    dispatch(e, "createProduct", ctx("p1"), product={"name": "أ", "sku": "DUP", "product_type": "ACCESSORY"})
    from shared.contracts.errors import DomainError
    import pytest
    with pytest.raises(DomainError) as exc:
        dispatch(e, "createProduct", ctx("p2"), product={"name": "ب", "sku": "DUP", "product_type": "ACCESSORY"})
    assert exc.value.code == "DUPLICATE_PRODUCT"


def test_dispatch_create_customer_and_supplier():
    e = ERPCommandEngine()
    customer = dispatch(e, "createCustomer", ctx("c1"), customer={"name": "أحمد", "phone": "0100"})
    assert customer.name == "أحمد" and e.customers.get("c1") is customer

    supplier = dispatch(e, "createSupplier", ctx("s1"), supplier={"name": "مورد أ"})
    assert supplier.name == "مورد أ" and e.suppliers.get("s1") is supplier


def test_dispatch_update_product_renames_and_changes_price():
    e = ERPCommandEngine()
    dispatch(e, "createProduct", ctx("p1"), product={"name": "شاحن", "sku": "SKU-1", "product_type": "ACCESSORY", "selling_price": "50"})
    updated = dispatch(e, "updateProduct", ctx("p2"), product_id="p1", changes={"name": "شاحن سريع", "selling_price": "75"})
    assert updated.name == "شاحن سريع"
    assert str(updated.selling_price) == "75.00"
    assert e.products.get("p1").name == "شاحن سريع"


def test_dispatch_update_product_not_found():
    e = ERPCommandEngine()
    from shared.contracts.errors import DomainError
    import pytest
    with pytest.raises(DomainError) as exc:
        dispatch(e, "updateProduct", ctx("p1"), product_id="missing", changes={"name": "x"})
    assert exc.value.code == "NOT_FOUND"


def test_dispatch_create_wallet():
    e = ERPCommandEngine()
    wallet = dispatch(e, "createWallet", ctx("w1", perms={"wallets.edit"}, branch="b1"),
                       wallet={"name": "الخزينة", "wallet_type": "CASH"})
    assert wallet.name == "الخزينة" and wallet.branch_id == "b1"
    assert e.wallets.get("w1") is wallet


def test_dispatch_create_wallet_rejects_duplicate_name_in_same_branch():
    e = ERPCommandEngine()
    dispatch(e, "createWallet", ctx("w1", perms={"wallets.edit"}, branch="b1"), wallet={"name": "الخزينة", "wallet_type": "CASH"})
    from shared.contracts.errors import DomainError
    import pytest
    with pytest.raises(DomainError) as exc:
        dispatch(e, "createWallet", ctx("w2", perms={"wallets.edit"}, branch="b1"), wallet={"name": "الخزينة", "wallet_type": "DIGITAL"})
    assert exc.value.code == "DUPLICATE_WALLET"


def test_dispatch_create_wallet_rejects_cross_branch_payload():
    """Even if the payload names a different branch_id, the command's own
    (authenticated) branch wins — create_wallet() rejects the mismatch
    rather than trusting the payload."""
    e = ERPCommandEngine()
    from shared.contracts.errors import DomainError
    import pytest
    with pytest.raises(DomainError) as exc:
        dispatch(e, "createWallet", ctx("w1", perms={"wallets.edit"}, branch="b1"),
                 wallet={"name": "الخزينة", "wallet_type": "CASH", "branch_id": "b2"})
    assert exc.value.code == "BRANCH_ACCESS_DENIED"


def test_dispatch_create_product_flat_payload_note():
    """Note: a flat (unwrapped) payload only works when none of its keys
    collide with dispatch()'s own positional parameters (engine/name/command)
    — and Product.name always collides with dispatch()'s 'name' parameter,
    so createProduct/createCustomer/createSupplier payloads must use the
    wrapper key ({'product': {...}}, etc.) shown in the other tests above.
    This is a pre-existing quirk of dispatch()'s **payload signature, not
    something this fix introduces or attempts to solve."""
    e = ERPCommandEngine()
    import pytest
    with pytest.raises(TypeError):
        dispatch(e, "createProduct", ctx("p1"), name="سماعة", sku="SKU-2", product_type="ACCESSORY")


def test_http_handle_create_product_end_to_end():
    e = ERPCommandEngine()

    def fake_auth(request):
        return {"uid": "u1", "tenant_id": "default", "branch_ids": {"b1"}, "permissions": {"products.edit"}}

    request = {
        "commandId": "p1",
        "command": "createProduct",
        "branchId": "b1",
        "payload": {"product": {"name": "شاحن", "sku": "SKU-9", "product_type": "ACCESSORY", "selling_price": "10"}},
    }
    response = handle(request, e, fake_auth)
    assert response["ok"] is True
    assert response["data"].sku == "SKU-9"


def test_http_handle_rejects_unauthenticated():
    """Matches the existing pattern in test_security_hardening.py
    (test_http_rejects_unassigned_branch): auth/branch checks in http.handle
    raise DomainError directly rather than being caught into the {'ok':
    False} shape — only dispatch()-level errors get that treatment. Keeping
    this test's expectation aligned with that existing, already-tested
    behavior rather than changing it."""
    from shared.contracts.errors import DomainError
    import pytest
    e = ERPCommandEngine()
    request = {"commandId": "p1", "command": "createProduct", "branchId": "b1", "payload": {}}
    with pytest.raises(DomainError) as exc:
        handle(request, e, lambda req: None)
    assert exc.value.code == "UNAUTHORIZED"
