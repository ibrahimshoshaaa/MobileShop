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
    "wallets.edit", "wallet.adjust", "expenses.create", "maintenance.create", "maintenance.parts",
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


def test_maintenance_transition_and_delivery():
    """sqlite_maintenance_repository.dart queues 'transitionMaintenance' with
    {'ticket_id', 'new_status'} to advance a ticket, and deliver_maintenance
    refuses delivery before the ticket reaches READY. Before dispatch.py's
    mapping included these two commands, both calls raised INVALID_INPUT
    ('الأمر غير مدعوم'), so a ticket queued offline could never be walked to
    READY/DELIVERED once it reached the server."""
    e = ERPCommandEngine()
    bootstrap(e)
    # Fund wallet-cash so the delivery payment below has a balance to draw on.
    run(e, "sale-fund", "createSale", customer_id="cust-1",
        items=[{"product_id": "p-1", "quantity": 2, "unit_price": 50}],
        payments=[{"wallet_id": "wallet-cash", "amount": 100}], discount=0)

    run(e, "mnt-1", "createMaintenanceTicket", customer_id="cust-1", device="Phone",
        problem="screen", imei=None)

    for step, next_status in enumerate(
        ("DIAGNOSING", "WAITING_CUSTOMER", "IN_PROGRESS", "READY")
    ):
        run(e, f"mnt-1-step-{step}", "transitionMaintenance",
            ticket_id="mnt-1", new_status=next_status)
    assert e.maintenance.get("mnt-1").status == "READY"

    run(e, "mnt-1-deliver", "deliverMaintenanceTicket", ticket_id="mnt-1",
        final_price=100, payment=100, wallet_id="wallet-cash")
    assert e.maintenance.get("mnt-1").status == "DELIVERED"


def test_maintenance_cancel_returns_used_parts_to_stock():
    """sqlite_maintenance_repository.dart queues 'cancelMaintenance' with just
    {'ticket_id'}; before it was mapped in dispatch.py this always failed with
    INVALID_INPUT, so a cancelled-locally ticket never actually cancelled (or
    returned its parts to stock) on the server."""
    e = ERPCommandEngine()
    bootstrap(e)
    run(e, "mnt-2", "createMaintenanceTicket", customer_id="cust-1", device="Phone",
        problem="battery", imei=None)
    run(e, "mntpart-2", "useMaintenancePart", ticket_id="mnt-2", product_id="p-1",
        quantity=2, cost=20)
    assert stock(e, "p-1") == 8

    run(e, "mnt-2-cancel", "cancelMaintenance", ticket_id="mnt-2")
    assert e.maintenance.get("mnt-2").status == "CANCELLED"
    assert stock(e, "p-1") == 10


def test_manual_wallet_deposit_and_withdraw_resolve_the_alias():
    """wallets/sqlite_wallet_repository.dart queues 'adjustWallet' with the
    fixed alias {'wallet_id': 'wallet-cash', 'amount': <signed>, 'reason'}
    for manual deposit/withdraw — the same alias every other command
    resolves to the caller's own branch wallet. Before dispatch.py resolved
    it here too, adjust_wallet's self._wallet(wallet_id, ...) would raise
    NOT_FOUND for the literal string 'wallet-cash'."""
    e = ERPCommandEngine()
    bootstrap(e)
    run(e, "wtx-1", "adjustWallet", wallet_id="wallet-cash", amount=100, reason="إيداع يدوي")
    run(e, "wtx-2", "adjustWallet", wallet_id="wallet-cash", amount=-30, reason="سحب يدوي")
    balance = e._balance("wallet-cash")
    assert balance == Decimal("70")


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
        payments=[{"wallet_id": "wallet-cash", "amount": 60}, {"wallet_id": "wallet-instapay", "amount": 40}],
        discount=0)
    assert [t for t, _ in _wallets(e)] == ["CASH", "INSTAPAY"]
    # reused, not duplicated, on the next command
    run(e, "sale-2", "createSale", customer_id=None,
        items=[{"product_id": "p-1", "quantity": 1, "unit_price": 50}],
        payments=[{"wallet_id": "wallet-cash", "amount": 50}], discount=0)
    assert [t for t, _ in _wallets(e)] == ["CASH", "INSTAPAY"]
    run(e, "exp-1", "createExpense", wallet_id="wallet-cash", amount=20, category="rent", note=None)


def test_legacy_card_alias_still_resolves_to_the_instapay_wallet():
    """Old installs (or already-queued offline commands from before Card
    was replaced by InstaPay) still send 'wallet-card'/'CARD'. Both must
    keep working — resolving to the same per-branch wallet 'wallet-instapay'
    now resolves to — rather than erroring or creating a separate BANK
    wallet no build sends payments to anymore."""
    e = _engine_with_product()
    run(e, "sale-legacy", "createSale", customer_id=None,
        items=[{"product_id": "p-1", "quantity": 1, "unit_price": 50}],
        payments=[{"wallet_id": "wallet-card", "amount": 50}], discount=0)
    assert [t for t, _ in _wallets(e)] == ["INSTAPAY"]


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


def test_installment_plan_with_down_payment_posts_to_the_chosen_wallet():
    """New admin_mobile shape (createPlan's downPaymentMethod, #4): a plan
    with a down payment sends down_payment_wallet_id as a built-in wallet
    alias, exactly like sqlite_installment_repository.dart's
    serverWalletRefForMethod does — resolved and posted the same way a
    sale's cash/wallet/instapay payment lines are."""
    e = _engine_with_product()
    PERMS2 = PERMS | {"installments.create"}
    # create_installment_plan requires the down-payment wallet to already
    # hold at least the down payment (same INSUFFICIENT_WALLET_BALANCE guard
    # collect_installment uses) — fund it first, as a real till would have
    # been funded by an earlier cash/instapay sale.
    run(e, "sale-fund", "createSale", customer_id=None,
        items=[{"product_id": "p-1", "quantity": 1, "unit_price": 50}],
        payments=[{"wallet_id": "wallet-instapay", "amount": 50}], discount=0)
    run(e, "sale-dp", "createSale", customer_id="cust-1",
        items=[{"product_id": "p-1", "quantity": 2, "unit_price": 50}], payments=[], discount=0)
    dispatch(e, "createInstallmentPlan", CommandContext("plan-dp", "u", BRANCH, PERMS2),
             sale_id="sale-dp", customer_id="cust-1", down_payment=30, rate_percent=5,
             term_months=3, down_payment_wallet_id="wallet-instapay")
    instapay = next(w for w in e.wallets.all() if w.wallet_type == "INSTAPAY")
    assert e._balance(instapay.id) == Decimal("80")
