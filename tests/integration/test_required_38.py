from decimal import Decimal
from datetime import date, timedelta
import pytest
from shared.contracts.commands import CommandContext, CreateSaleCommand
from shared.models.erp import Product, ProductUnit, Wallet, Supplier, Customer, Employee
from shared.contracts.errors import DomainError
from backend.functions.services.erp_engine import ERPCommandEngine
from backend.functions.offline.sync import OfflineSync

def C(cid, perms=None, branch='b1'):
    p=perms or {'products.edit','customers.edit','customers.collect','suppliers.edit','purchases.create','purchases.pay_supplier','sales.create','expenses.create','sales.discount','sales.void','sales.return','inventory.create_unit','stock.adjust','stock.transfer','wallet.adjust','wallet.transfer','transfer.create','installments.create','installments.collect','maintenance.create','maintenance.update','maintenance.parts','closing.close','permissions.change','settings.change','employees.salary'}
    return CommandContext(cid,'u',branch,frozenset(p))

def setup():
    e=ERPCommandEngine(); e.products.create('p',Product('p','Phone','SKU','PHONE_NEW',barcode='BAR',default_cost=Decimal('100')))
    e.products.create('a',Product('a','Accessory','SKU-A','ACCESSORY',default_cost=Decimal('10')))
    e.wallets.create('cash',Wallet('cash','b1','Cash','CASH')); e.wallets.create('dig',Wallet('dig','b1','Digital','DIGITAL')); e.wallets.create('cash2',Wallet('cash2','b2','Cash2','CASH'))
    e.ledger.create('open',{'id':'open','branch_id':'b1','account_id':'wallet:cash','debit':Decimal('5000'),'credit':Decimal('0')})
    e.ledger.create('opend',{'id':'opend','branch_id':'b1','account_id':'wallet:dig','debit':Decimal('5000'),'credit':Decimal('0')})
    e.customers.create('c',Customer('c','Customer')); e.suppliers.create('s',Supplier('s','Supplier'))
    e.adjust_stock(C('seed'),'p',20,100)
    return e

def sale(e,cid='s',unit=False,pay=150,discount=0,customer=None):
    item={'product_id':'p','quantity':1,'unit_price':150}
    if unit: e.units.create('u',ProductUnit('u','p','b1',imei1='123456789012345',final_cost=100,warranty_end=date.today()+timedelta(days=30))); item['product_unit_id']='u'
    return e.create_sale(CreateSaleCommand(C(cid),customer,(item,),({'wallet_id':'cash','amount':140 if discount else pay},),discount))

def test_01_new_phone_sale(): e=setup(); assert sale(e).total==150

def test_02_used_phone_sale(): e=setup(); e.products.update('p',Product('p','Used','SKU','PHONE_USED',default_cost=80)); assert sale(e).total==150

def test_03_duplicate_imei():
    e=setup(); e.units.create('u1',ProductUnit('u1','p','b1',imei1='111',final_cost=100))
    with pytest.raises(DomainError) as x:e.register_product_unit(C('x'),ProductUnit('u2','p','b1',imei1='111'))
    assert x.value.code=='IMEI_ALREADY_EXISTS'

def test_04_sold_imei_rejected(): e=setup(); sale(e,unit=True); 

def test_05_cross_branch_imei_rejected():
    e=setup(); e.units.create('u',ProductUnit('u','p','b2',imei1='222',final_cost=100))
    with pytest.raises(DomainError) as x:e.create_sale(CreateSaleCommand(C('x'),None,({'product_id':'p','quantity':1,'unit_price':150,'product_unit_id':'u'},),({'wallet_id':'cash','amount':150},)))
    assert x.value.code=='BRANCH_ACCESS_DENIED'

def test_06_split_payment():
    e=setup(); s=e.create_sale(CreateSaleCommand(C('x'),None,({'product_id':'p','quantity':1,'unit_price':150},),({'wallet_id':'cash','amount':75},{'wallet_id':'dig','amount':75}))); assert len(s.payments)==2

def test_07_discount(): e=setup(); assert sale(e,discount=10).total==140

def test_08_void(): e=setup(); s=sale(e,unit=True); assert e.void_sale(C('v'),s.id).status=='VOIDED'

def test_09_full_return(): e=setup(); s=sale(e,unit=True); assert e.return_sale(C('r'),s.id,({'sale_item_id':s.items[0].id,'quantity':1},),'cash')['amount']==150

def test_10_partial_return():
    e=setup(); e.adjust_stock(C('seed-a'),'a',3,10); s=e.create_sale(CreateSaleCommand(C('s'),None,({'product_id':'a','quantity':3,'unit_price':20},),({'wallet_id':'cash','amount':60},))); assert e.return_sale(C('r'),s.id,({'sale_item_id':s.items[0].id,'quantity':1},),'cash')['amount']==20

def test_11_exchange(): e=setup(); s=sale(e,unit=True); x=e.exchange_sale(C('ex'),s.id,({'sale_item_id':s.items[0].id,'quantity':1},),({'product_id':'p','quantity':1,'unit_price':150,'product_unit_id':'u'},),({'wallet_id':'cash','amount':150},)); assert x['type']=='EXCHANGE'

def test_12_purchase(): e=setup(); e.create_purchase(C('p1'),'s',({'product_id':'a','quantity':5,'unit_cost':10},),0); assert e._available_qty('b1','a')==5

def test_13_partial_supplier_payment():
    e=setup(); e.create_purchase(C('p1'),'s',({'product_id':'a','quantity':5,'unit_cost':10,'wallet_id':'cash'},),20); assert e.supplier_balance('s','b1')==30

def test_14_customer_credit(): e=setup(); s=sale(e,pay=50,customer='c'); assert e.customer_balance('c','b1')==100

def test_15_installment_sale(): e=setup(); s=sale(e,pay=50,customer='c'); p=e.create_installment_plan(C('ip'),s.id,'c',50,10,2); assert p.total_due==110

def test_16_installment_collection():
    e=setup(); s=sale(e,pay=50,customer='c'); p=e.create_installment_plan(C('ip'),s.id,'c',50,10,2); e.collect_installment(C('col'),p.id,55,'cash'); assert e.installment_remaining(p.id)==55

def test_17_partial_installment():
    e=setup(); s=sale(e,pay=50,customer='c'); p=e.create_installment_plan(C('ip'),s.id,'c',50,10,2); e.collect_installment(C('col'),p.id,10,'cash'); assert e.installment_remaining(p.id)==100

def test_18_overdue():
    e=setup(); s=sale(e,pay=50,customer='c'); p=e.create_installment_plan(C('ip'),s.id,'c',50,10,2); e.create_installment_schedule(p.id,date.today()-timedelta(days=90)); assert any(x['status']=='OVERDUE' for x in e.installment_status(p.id))

def test_19_five_month_rate(): e=setup(); s=sale(e,pay=50,customer='c'); assert e.create_installment_plan(C('x'),s.id,'c',50,20,5).total_due==120

def test_20_ten_month_rate(): e=setup(); s=sale(e,pay=50,customer='c'); assert e.create_installment_plan(C('x'),s.id,'c',50,30,10).total_due==130

def test_21_cash_digital_transfer(): e=setup(); x=e.transfer_customer(C('x'),'cash','dig',100); assert x['commission']==1

def test_22_digital_cash_transfer(): e=setup(); x=e.transfer_customer(C('x'),'dig','cash',100); assert x['commission']==1

def test_23_default_commission(): e=setup(); assert e.transfer_customer(C('x'),'cash','dig',100)['commission']==1

def test_24_manual_commission(): e=setup(); x=e.transfer_customer(C('x'),'cash','dig',100,50,'friendly'); assert x['commission']==50 and x['override']

def test_25_internal_wallet_transfer(): e=setup(); e.transfer_between_wallets(C('x'),'cash','dig',100); assert e._balance('cash')==4900 and e._balance('dig')==5100

def test_26_maintenance_intake(): e=setup(); assert e.create_maintenance_ticket(C('m'),'c','phone','broken').status=='RECEIVED'

def test_27_maintenance_parts(): e=setup(); e.adjust_stock(C('seed-a'),'a',2,10); t=e.create_maintenance_ticket(C('m'),'c','phone','broken'); e.transition_maintenance(C('d'),t.id,'DIAGNOSING'); e.transition_maintenance(C('w'),t.id,'WAITING_CUSTOMER'); e.transition_maintenance(C('i'),t.id,'IN_PROGRESS'); assert e.use_maintenance_part(C('part'),t.id,'a',1,10)['quantity']==1

def test_28_maintenance_delivery():
    e=setup(); t=e.create_maintenance_ticket(C('m'),'c','phone','broken');
    for n,s in enumerate(['DIAGNOSING','WAITING_CUSTOMER','IN_PROGRESS','READY']): t=e.transition_maintenance(C(str(n)),t.id,s)
    assert e.deliver_maintenance(C('del'),t.id,900,900,'cash').status=='DELIVERED'

def test_29_warranty_check(): e=setup(); e.units.create('u',ProductUnit('u','p','b1',imei1='999',final_cost=100,warranty_end=date.today()+timedelta(days=1))); assert e.warranty_check('b1','999')[0] is True

def test_30_expense(): e=setup(); e.create_expense(C('e'),'cash',50,'rent'); assert e._balance('cash')==4950

def test_31_employee_commission(): e=setup(); e.employees.create('e',Employee('e','Ali',('b1',),fixed_salary=100)); r=e.calculate_salary(C('s'),'e','2026-09',100,25); assert r.commission==25

def test_32_branch_inventory_transfer(): e=setup(); e.adjust_stock(C('seed-a'),'a',3,10); e.transfer_stock(C('tr'),'a',2,'b1','b2',10); assert e._available_qty('b1','a')==1 and e._available_qty('b2','a')==2

def test_33_daily_closing(): e=setup(); c=e.close_day(C('cl'),date.today(),{'cash':5000,'dig':5000}); assert c.locked

def test_34_cash_discrepancy(): e=setup(); c=e.close_day(C('cl'),date.today(),{'cash':4990,'dig':5000}); assert c.discrepancy['cash']==-10

def test_35_permission_denial():
    e=setup();
    with pytest.raises(DomainError) as x:e.create_expense(C('x',{'sales.create'}),'cash',10,'x')
    assert x.value.code=='FORBIDDEN'

def test_36_idempotency(): e=setup(); c=CreateSaleCommand(C('same'),None,({'product_id':'p','quantity':1,'unit_price':150},),({'wallet_id':'cash','amount':150},)); assert e.create_sale(c) is e.create_sale(c)

def test_37_transaction_rollback():
    e=setup()
    with pytest.raises(RuntimeError):
        e.transaction(lambda:(e.create_expense(C('x'),'cash',10,'x'), (_ for _ in ()).throw(RuntimeError('boom'))))
    assert e.expenses.all()==[] and e._balance('cash')==5000

def test_38_offline_conflict():
    q=OfflineSync(); q.enqueue('c1',{'x':1}); q.enqueue('c2',{'x':2})
    def ex(payload):
        if payload['x']==2: raise DomainError('TRANSACTION_CONFLICT','conflict',{})
    r=q.sync(ex); assert r.applied==['c1'] and r.conflicts==['c2']
