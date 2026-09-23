"""End-to-end contract between what apps/admin_mobile queues/pushes and what
backend/functions/api/dispatch.py accepts.

Every payload below is exactly the shape the Flutter repositories send (see
sqlite_*_repository.dart). The scenario replays them in the order a real device
would, using ONLY commands the client queues, and checks the server ends up
consistent. Regressions this guards against:
  * server storing products/customers under the command id instead of the
    client-generated id (later commands then failed with NOT_FOUND);
  * updateProduct/updateCustomer sending a flat payload the server rejected;
  * a sale/void/maintenance-part being applied to stock twice (once by the
    command itself, once by a redundant client-queued adjustStock).
"""
from decimal import Decimal

from backend.functions.api.dispatch import dispatch
from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.commands import CommandContext

PERMS = frozenset({
    "products.edit", "customers.edit", "stock.adjust", "sales.create", "sales.void",
    "wallets.edit", "expenses.create", "maintenance.create", "maintenance.parts",
    "maintenance.update",
})
BRANCH = "b1"


def run(engine, cmd_id, command, **payload):
    return dispatch(engine, command, CommandContext(cmd_id, "u", BRANCH, PERMS), **payload)


def stock(engine, product_id):
    return engine._available_qty(BRANCH, product_id)


def bootstrap(engine):
    run(engine, "wallet-cash", "createWallet",
        wallet={"name": "cash", "wallet_type": "CASH", "branch_id": BRANCH})
    run(engine, "cmd-create-1", "createProduct", id="p-1", name="Cable", sku="C1",
        product_type="ACCESSORY", selling_price=50, default_cost=20, quantity=10)
    run(engine, "cmd-stock-1", "adjustStock", product_id="p-1", delta=10, reason="opening")
    run(engine, "cmd-create-cust-1", "createCustomer", id="cust-1", name="Ali", phone="0100")


def test_client_ids_are_used_and_opening_stock_applies():
    e = ERPCommandEngine()
    bootstrap(e)
    assert e.products.get("p-1") is not None
    assert e.customers.get("cust-1") is not None
    assert stock(e, "p-1") == 10


def test_flat_updates_from_client_are_accepted():
    e = ERPCommandEngine()
    bootstrap(e)
    # sqlite_inventory_repository.updateProduct sends the whole product, incl. quantity
    run(e, "cmd-update-1", "updateProduct", id="p-1", name="Cable v2", sku="C1",
        product_type="ACCESSORY", barcode=None, selling_price=60.5, default_cost=20,
        reorder_level=2, quantity=999, active=True)
    p = e.products.get("p-1")
    assert p.name == "Cable v2" and p.selling_price == Decimal("60.50")
    assert stock(e, "p-1") == 10  # quantity is never settable through updateProduct
    run(e, "cmd-update-cust-1", "updateCustomer", id="cust-1", name="Ali B", phone="0100", active=True)
    assert e.customers.get("cust-1").name == "Ali B"


def test_sale_void_and_maintenance_move_stock_exactly_once():
    e = ERPCommandEngine()
    bootstrap(e)
    # Client queues only createSale now (no extra adjustStock).
    run(e, "sale-1", "createSale", customer_id="cust-1",
        items=[{"product_id": "p-1", "quantity": 2, "unit_price": 50}],
        payments=[{"wallet_id": "wallet-cash", "amount": 100}], discount=0)
    assert stock(e, "p-1") == 8
    run(e, "cmd-void-1", "voidSale", sale_id="sale-1")
    assert stock(e, "p-1") == 10

    run(e, "mnt-1", "createMaintenanceTicket", customer_id="cust-1", device="Phone",
        problem="screen", imei=None)
    run(e, "mntpart-1", "useMaintenancePart", ticket_id="mnt-1", product_id="p-1", quantity=3, cost=20)
    assert stock(e, "p-1") == 7


def test_expense_uses_real_wallet_id():
    e = ERPCommandEngine()
    bootstrap(e)
    run(e, "sale-1", "createSale", customer_id=None,
        items=[{"product_id": "p-1", "quantity": 1, "unit_price": 50}],
        payments=[{"wallet_id": "wallet-cash", "amount": 50}], discount=0)
    run(e, "exp-1", "createExpense", wallet_id="wallet-cash", amount=10, category="rent", note=None)


def test_clients_do_not_queue_a_second_stock_command_for_sales_voids_and_maintenance():
    """createSale / voidSale / useMaintenancePart already move stock on the server.
    Their local stock change must therefore not queue its own adjustStock, or the
    stock is applied twice after sync. (Source-level guard: the Flutter code can't
    run in this suite.)"""
    import re
    from pathlib import Path
    dart = Path(__file__).resolve().parents[2] / "apps/admin_mobile/lib/features"
    for rel in ("sales/sqlite_sale_repository.dart", "maintenance/sqlite_maintenance_repository.dart"):
        calls = re.findall(r"_inventory\.adjustStock\([^;]*;", (dart / rel).read_text(encoding="utf-8"))
        assert calls, rel
        assert all("queueSync: false" in c for c in calls), (rel, calls)


# --- built-in wallets, legacy payload shapes -------------------------------

def _engine_with_product():
    e = ERPCommandEngine()
    run(e, "cmd-create-1", "createProduct", id="p-1", name="Cable", sku="C1",
        product_type="ACCESSORY", selling_price=50, default_cost=20)
    run(e, "cmd-stock-1", "adjustStock", product_id="p-1", delta=10, reason="opening")
    run(e, "cmd-create-cust-1", "createCustomer", id="cust-1", name="Ali")
    return e


def _wallets(e, branch=BRANCH):
    return sorted((w.wallet_type, w.name) for w in e.wallets.all() if w.branch_id == branch)


def test_builtin_wallets_are_provisioned_on_first_use_without_createwallet():
    e = _engine_with_product()
    assert _wallets(e) == []
    run(e, "sale-1", "createSale", customer_id=None,
        items=[{"product_id": "p-1", "quantity": 2, "unit_price": 50}],
        payments=[{"wallet_id": "wallet-cash", "amount": 60}, {"wallet_id": "wallet-card", "amount": 40}],
        discount=0)
    assert [t for t, _ in _wallets(e)] == ["BANK", "CASH"]
    # reused, not duplicated, on the next command
    run(e, "sale-2", "createSale", customer_id=None,
        items=[{"product_id": "p-1", "quantity": 1, "unit_price": 50}],
        payments=[{"wallet_id": "wallet-cash", "amount": 50}], discount=0)
    assert [t for t, _ in _wallets(e)] == ["BANK", "CASH"]
    run(e, "exp-1", "createExpense", wallet_id="wallet-cash", amount=20, category="rent", note=None)


def test_wallets_are_per_branch_even_though_the_client_alias_is_fixed():
    e = _engine_with_product()
    dispatch(e, "adjustStock", CommandContext("stock-b2", "u", "b2", PERMS),
             product_id="p-1", delta=5, reason="opening b2")   # stock is tracked per branch
    for branch, sale_id in (("b1", "s1"), ("b2", "s2")):
        dispatch(e, "createSale", CommandContext(sale_id, "u", branch, PERMS), customer_id=None,
                 items=[{"product_id": "p-1", "quantity": 1, "unit_price": 50}],
                 payments=[{"wallet_id": "wallet-cash", "amount": 50}], discount=0)
    cash = [w for w in e.wallets.all() if w.wallet_type == "CASH"]
    assert sorted(w.branch_id for w in cash) == ["b1", "b2"]
    assert len({w.id for w in cash}) == 2


def test_legacy_queued_shapes_still_apply():
    e = _engine_with_product()
    # Old builds queued payments as {'method', 'amount'} (+ extra keys) and CREDIT lines.
    run(e, "sale-old", "createSale", customer_id="cust-1", customer_name="Ali",
        items=[{"product_id": "p-1", "product_name": "Cable", "quantity": 2, "unit_price": 50,
                "cost_at_sale": 20, "cost_is_estimated": False}],
        payments=[{"method": "CASH", "amount": 60}, {"method": "CREDIT", "amount": 40}], discount=0)
    assert stock(e, "p-1") == 8
    # ...and the extra adjustStock they queued next to it must not deduct again.
    res = run(e, "cmd-stock-old", "adjustStock", product_id="p-1", delta=-2,
              reason="بيع فاتورة #sale-1758000000000000-123456")
    assert res["skipped"] is True
    assert stock(e, "p-1") == 8
    run(e, "cmd-stock-mnt", "adjustStock", product_id="p-1", delta=-1, reason="استخدام في صيانة #mnt-1-2")
    assert stock(e, "p-1") == 8
    # a genuine manual adjustment still applies
    run(e, "cmd-stock-manual", "adjustStock", product_id="p-1", delta=-1, reason="جرد: تالف")
    assert stock(e, "p-1") == 7
    # legacy expense used the method name as wallet id
    run(e, "exp-old", "createExpense", wallet_id="CASH", amount=10, category="rent", note=None)


def test_legacy_installment_plan_shape_is_trimmed_and_local_only_plans_rejected_cleanly():
    import pytest
    from shared.contracts.errors import DomainError
    e = _engine_with_product()
    PERMS2 = PERMS | {"installments.create"}
    def go(cid, **kw):
        return dispatch(e, "createInstallmentPlan", CommandContext(cid, "u", BRANCH, PERMS2), **kw)
    with pytest.raises(DomainError) as exc:   # standalone plan (no sale): cannot exist server-side
        go("plan-1", id="plan-1", sale_id=None, customer_id="cust-1", customer_name="Ali",
           base_financed=100, rate_percent=5, increase=5, total_due=105, term_months=3, monthly_amount=35)
    assert exc.value.code == "INVALID_INPUT"
    run(e, "sale-i", "createSale", customer_id="cust-1",
        items=[{"product_id": "p-1", "quantity": 2, "unit_price": 50}], payments=[], discount=0)
    plan = go("plan-2", id="plan-2", sale_id="sale-i", customer_id="cust-1", customer_name="Ali",
              base_financed=100, rate_percent=5, increase=5, total_due=105, term_months=3, monthly_amount=35)
    assert plan.sale_id == "sale-i"
