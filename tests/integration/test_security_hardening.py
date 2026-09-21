import pytest
from decimal import Decimal
from backend.functions.api.http import handle
from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.errors import DomainError

class Req:
    def __init__(self, data): self.data=data
    def get_json(self, silent=True): return self.data

def verified(_):
    return {'uid':'u1','tenant_id':'default','branch_ids':['b1'],'permissions':['sales.create']}

def test_http_uses_trusted_permissions_not_payload():
    e=ERPCommandEngine()
    req=Req({'commandId':'x','command':'createSale','branchId':'b1',
             'payload':{'auth':{'uid':'attacker','permissions':['OWNER']}}})
    out=handle(req,e,verified)
    assert out['ok'] is False
    assert out['error']['code']=='INVALID_INPUT'

def test_http_rejects_unassigned_branch():
    e=ERPCommandEngine()
    req=Req({'commandId':'x','command':'createSale','branchId':'b9','payload':{}})
    with pytest.raises(DomainError) as exc: handle(req,e,verified)
    assert exc.value.code=='BRANCH_ACCESS_DENIED'

def test_customer_transfer_override_is_authorized_by_transfer_permission():
    e=ERPCommandEngine()
    from shared.models.erp import Wallet
    from shared.contracts.commands import CommandContext
    e.wallets.create('cash', Wallet('cash','b1','Cash','CASH'))
    e.wallets.create('dig', Wallet('dig','b1','Digital','DIGITAL'))
    e.ledger.create('seed', {'id':'seed','branch_id':'b1','account_id':'wallet:dig','entry_type':'SEED','debit':1000,'credit':0})
    x=e.transfer_customer(CommandContext('t','u','b1',frozenset({'transfer.create'})),'cash','dig',100,50)
    assert x['commission']==50 and x['override'] is True

def test_customer_transfer_digital_to_cash_moves_in_correct_direction():
    e=ERPCommandEngine()
    from shared.models.erp import Wallet
    from shared.contracts.commands import CommandContext
    e.wallets.create('cash', Wallet('cash','b1','Cash','CASH'))
    e.wallets.create('dig', Wallet('dig','b1','Digital','DIGITAL'))
    e.ledger.create('seed-d', {'id':'seed-d','branch_id':'b1','account_id':'wallet:dig','entry_type':'SEED','debit':1000,'credit':0})
    e.ledger.create('seed-c', {'id':'seed-c','branch_id':'b1','account_id':'wallet:cash','entry_type':'SEED','debit':200,'credit':0})
    x=e.transfer_customer(CommandContext('t','u','b1',frozenset({'transfer.create'})),'dig','cash',100)
    assert x['commission']==1
    assert e._balance('dig')==1100
    assert e._balance('cash')==99
    assert e.ledger_transaction_totals('t') == (Decimal('101.00'), Decimal('101.00'))


def test_idempotency_is_scoped_to_tenant():
    from shared.contracts.commands import CommandContext
    from shared.models.erp import Product

    e = ERPCommandEngine()
    p1 = Product("p-tenant-a", "A", "SKU-A", "ACCESSORY")
    p2 = Product("p-tenant-b", "B", "SKU-B", "ACCESSORY")

    e.create_product(CommandContext("same-command", "u1", "b1", frozenset({"products.edit"}), "tenant-a"), p1)
    result = e.create_product(CommandContext("same-command", "u2", "b1", frozenset({"products.edit"}), "tenant-b"), p2)

    assert result.id == "p-tenant-b"
    assert e.products.get("p-tenant-a") is None
    assert e.products.get("p-tenant-b") is p2
