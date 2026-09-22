import pytest
from decimal import Decimal
from backend.functions.services.erp_engine import ERPCommandEngine
from shared.models.erp import Wallet, Product, StockMovement
from shared.contracts.commands import CommandContext, CreateSaleCommand
from shared.contracts.errors import DomainError

def ctx(cid, perms): return CommandContext(cid,'u','b1',frozenset(perms))

def setup():
    e=ERPCommandEngine(); e.wallets.create('w',Wallet('w','b1','Cash','CASH'))
    e.ledger.create('seed',{'id':'seed','branch_id':'b1','account_id':'wallet:w','entry_type':'SEED','debit':1000,'credit':0})
    e.products.create('p',Product('p','Phone','SKU-P','PHONE_NEW',default_cost=100))
    e.stock.create('in', StockMovement('in','b1','p',2,'PURCHASE','in',None,100))
    return e

def test_return_rejects_duplicate_quantity():
    e=setup(); c=ctx('sale',{'sales.create'})
    sale=e.create_sale(CreateSaleCommand(c,None,({'product_id':'p','quantity':1,'unit_price':200},),({'wallet_id':'w','amount':200},),0))
    e.return_sale(ctx('r1',{'sales.return'}),sale.id,[{'product_id':'p','quantity':1}], 'w')
    with pytest.raises(DomainError) as ex:
        e.return_sale(ctx('r2',{'sales.return'}),sale.id,[{'product_id':'p','quantity':1}], 'w')
    assert ex.value.code=='INVALID_RETURN'

def test_return_rejects_cross_branch():
    e=setup(); c=ctx('sale',{'sales.create'})
    sale=e.create_sale(CreateSaleCommand(c,None,({'product_id':'p','quantity':1,'unit_price':200},),({'wallet_id':'w','amount':200},),0))
    with pytest.raises(DomainError) as ex:
        e.return_sale(ctx('r1',{'sales.return'})._replace(branch_id='b2') if False else CommandContext('r1','u','b2',frozenset({'sales.return'})),sale.id,[{'product_id':'p','quantity':1}],'w')
    assert ex.value.code=='BRANCH_ACCESS_DENIED'
