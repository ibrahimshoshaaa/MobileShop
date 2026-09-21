from decimal import Decimal
from datetime import date
import pytest
from shared.contracts.commands import CommandContext, CreateSaleCommand
from shared.models.erp import Product, ProductUnit, Wallet, Employee, Customer
from shared.contracts.errors import DomainError
from backend.functions.services.erp_engine import ERPCommandEngine

def ctx(cid, perms=None):
    p=perms or {'sales.create','sales.void','sales.return','purchases.create','purchases.pay_supplier','expenses.create','stock.adjust','stock.transfer','wallet.transfer','wallet.adjust','transfer.create','installments.create','installments.collect','maintenance.create','maintenance.update','maintenance.parts','closing.close','inventory.create_unit','permissions.change','settings.change','employees.salary'}
    return CommandContext(cid,'u','b1',frozenset(p))
def base():
    e=ERPCommandEngine(); e.customers.create('c', Customer('c','Test Customer')); e.products.create('p',Product('p','Phone','S','PHONE_NEW',default_cost=Decimal('100'))); e.wallets.create('w',Wallet('w','b1','Cash','CASH')); e.wallets.create('w2',Wallet('w2','b1','Bank','DIGITAL')); e.ledger.create('open',{'id':'open','account_id':'wallet:w','debit':Decimal('500'),'credit':Decimal('0')})
    return e

def test_imei_duplicate_and_sale_stock():
    e=base(); c=ctx('u1'); u=ProductUnit('u','p','b1',imei1='123',final_cost=Decimal('100')); e.register_product_unit(c,u)
    with pytest.raises(DomainError) as x:e.register_product_unit(ctx('u2'),ProductUnit('u2','p','b1',imei1='123'))
    assert x.value.code=='IMEI_ALREADY_EXISTS'

def test_void_restores_unit():
    e=base(); e.units.create('u',ProductUnit('u','p','b1',imei1='1',final_cost=Decimal('100')))
    s=e.create_sale(CreateSaleCommand(ctx('s'),None,({'product_id':'p','quantity':1,'unit_price':Decimal('150'),'product_unit_id':'u'},),({'wallet_id':'w','amount':Decimal('150')},)))
    v=e.void_sale(ctx('v'),s.id); assert v.status=='VOIDED' and e.units.get('u').status=='AVAILABLE'

def test_return():
    e=base(); e.units.create('u',ProductUnit('u','p','b1',imei1='1',final_cost=Decimal('100')))
    s=e.create_sale(CreateSaleCommand(ctx('s'),None,({'product_id':'p','quantity':1,'unit_price':Decimal('150'),'product_unit_id':'u'},),({'wallet_id':'w','amount':Decimal('150')},)))
    r=e.return_sale(ctx('r'),s.id,({'sale_item_id':s.items[0].id,'quantity':1},),'w'); assert r['amount']==Decimal('150.00')

def test_wallet_transfer_and_adjustment():
    e=base(); e.transfer_between_wallets(ctx('t'),'w','w2',Decimal('100')); assert e._balance('w')==399 and e._balance('w2')==100; e.adjust_wallet(ctx('a'),'w',Decimal('20')); assert e._balance('w')==419

def test_customer_transfer_commission_is_revenue_only():
    e=base(); x=e.create_transfer(ctx('tr'),'w','w2',Decimal('100'),Decimal('2')); assert x['commission']==2; assert e._balance('w')==400 and e._balance('w2')==100; assert any((z['account_id'] if isinstance(z,dict) else z.account_id)=='transfer_commission' and (z['credit'] if isinstance(z,dict) else z.credit)==2 for z in e.ledger.all())

def test_installment_rounding_and_collection():
    e=base(); e.adjust_stock(ctx('seed'), 'p', 1, Decimal('100')); s=e.create_sale(CreateSaleCommand(ctx('s'),'c',({'product_id':'p','quantity':1,'unit_price':Decimal('300')},),({'wallet_id':'w','amount':Decimal('100')},)))
    p=e.create_installment_plan(ctx('i'),s.id,'c',Decimal('100'),Decimal('10'),2); assert p.base_financed==100 and p.increase==10 and p.total_due==110 and p.monthly_amount==55
    e.collect_installment(ctx('ip'),'i',Decimal('55'),'w'); assert e.installment_remaining('i')==55

def test_maintenance_flow_and_part_usage():
    e=base(); e.adjust_stock(ctx('st'),'p',5,Decimal('100')); t=e.create_maintenance_ticket(ctx('m'),'c','device','broken');
    for i,n in enumerate(['DIAGNOSING','WAITING_CUSTOMER','IN_PROGRESS']): t=e.transition_maintenance(ctx(f'm{i}'),t.id,n)
    e.use_maintenance_part(ctx('part'),t.id,'p',1,Decimal('100')); assert e.maintenance.get(t.id).parts_cost==100

def test_daily_closing_and_reports():
    e=base(); e.create_expense(ctx('ex'),'w',Decimal('50'),'rent'); c=e.close_day(ctx('cl'),date.today(),{'w':450,'w2':0}); assert c.locked; r=e.reports('b1'); assert r['wallet_balances']['w']==450

def test_salary_payment():
    e=base(); e.employees.create('e',Employee('e','Ali',('b1',),fixed_salary=Decimal('200'))); r=e.calculate_salary(ctx('sal'),'e','2026-09',200,10,5,15); p=e.pay_salary(ctx('pay'),r.id,'w'); assert p.paid==200


def test_daily_closing_freezes_operations_until_reopened():
    e=base()
    e.close_day(ctx('close'),date.today(),{'w':500,'w2':0})
    with pytest.raises(DomainError) as x:
        e.create_expense(ctx('blocked'),'w',Decimal('10'),'after close')
    assert x.value.code=='DAY_CLOSED'
    reopened=e.reopen_day(CommandContext('reopen','u','b1',frozenset({'closing.reopen'})),date.today())
    assert reopened.locked is False
    e.create_expense(ctx('allowed'),'w',Decimal('10'),'after reopen')
    assert e._balance('w')==Decimal('490')
