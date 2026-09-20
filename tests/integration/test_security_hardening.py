import pytest
from backend.functions.api.http import handle
from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.errors import DomainError

class Req:
    def __init__(self, data): self.data=data
    def get_json(self, silent=True): return self.data

def verified(_):
    return {'uid':'u1','branch_ids':['b1'],'permissions':['sales.create']}

def test_http_uses_trusted_permissions_not_payload():
    e=ERPCommandEngine()
    req=Req({'commandId':'x','command':'createSale','branchId':'b1',
             'auth':{'uid':'attacker','permissions':['OWNER']},'payload':{}})
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
    assert e._balance('cash')==100
