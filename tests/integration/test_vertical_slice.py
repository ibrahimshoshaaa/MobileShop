from decimal import Decimal
import pytest
from shared.contracts.commands import CommandContext, CreateSaleCommand
from shared.models.erp import Product, ProductUnit, Wallet, LedgerEntry
from backend.functions.services.erp_engine import ERPCommandEngine
from shared.contracts.errors import DomainError

CTX=lambda cid, perms=frozenset({'sales.create','purchases.create','expenses.create'}): CommandContext(cid,'u1','b1',perms)

def seeded():
    e=ERPCommandEngine(); e.products.create('p1',Product('p1','iPhone','SKU1','PHONE_NEW',default_cost=Decimal('500')))
    e.units.create('u1',ProductUnit('u1','p1','b1',imei1='111',purchase_cost=Decimal('500'),final_cost=Decimal('500')))
    e.wallets.create('cash',Wallet('cash','b1','Cash','CASH'))
    # opening balance
    e.ledger.create('opening',LedgerEntry('opening','b1','wallet:cash','OPENING',debit=Decimal('1000')))
    return e

def test_sale_is_atomic_domain_slice():
    e=seeded(); c=CreateSaleCommand(CTX('sale1'),None,({'product_id':'p1','quantity':1,'unit_price':Decimal('700'),'product_unit_id':'u1'},),({'wallet_id':'cash','amount':Decimal('700')},))
    s=e.create_sale(c)
    assert s.total==Decimal('700'); assert e.units.get('u1').status=='SOLD'; assert e._balance('cash')==Decimal('1700')
    assert len(e.audit.all())==1

def test_sale_rejects_wrong_payment_without_mutation():
    e=seeded(); c=CreateSaleCommand(CTX('bad'),None,({'product_id':'p1','quantity':1,'unit_price':Decimal('700'),'product_unit_id':'u1'},),({'wallet_id':'cash','amount':Decimal('600')},))
    with pytest.raises(DomainError) as x: e.create_sale(c)
    assert x.value.code=='INVALID_PAYMENT'; assert e.sales.all()==[]; assert e.units.get('u1').status=='AVAILABLE'

def test_idempotency_returns_same_result():
    e=seeded(); c=CreateSaleCommand(CTX('same'),None,({'product_id':'p1','quantity':1,'unit_price':Decimal('700'),'product_unit_id':'u1'},),({'wallet_id':'cash','amount':Decimal('700')},))
    a=e.create_sale(c); b=e.create_sale(c); assert a is b; assert len(e.sales.all())==1
