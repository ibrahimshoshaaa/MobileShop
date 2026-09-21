from __future__ import annotations
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from threading import RLock
from shared.models.erp import *
from shared.contracts.errors import DomainError
from backend.functions.repositories.generic import Repository, set_tenant_scope, reset_tenant_scope

D0=Decimal('0'); CENT=Decimal('0.01')
def _ctx(command): return getattr(command, "context", command)
def dec(v): return Decimal(str(v))
def money(v): return dec(v).quantize(CENT, rounding=ROUND_HALF_UP)

class ERPCommandEngine:
    """Reference server-side command engine.

    All public commands follow: auth -> validation -> branch checks -> idempotency
    -> locked atomic mutation -> audit. Repositories are intentionally swappable;
    the bundled implementation is deterministic/in-memory for tests and local dev.
    """
    def __init__(self):
        self.products=Repository(); self.units=Repository(); self.sales=Repository(); self.purchases=Repository()
        self.wallets=Repository(); self.ledger=Repository(); self.stock=Repository(); self.expenses=Repository(); self.audit=Repository()
        self.customers=Repository(); self.suppliers=Repository(); self.installments=Repository(); self.installment_payments=Repository()
        self.maintenance=Repository(); self.maintenance_parts=Repository(); self.employees=Repository(); self.salary_records=Repository(); self.closings=Repository()
        self.transfers=Repository(); self.returns=Repository(); self.settings=Repository(); self.catalog=Repository(); self._processed={}; self._lock=RLock()

    def _auth(self,ctx,perm):
        if not getattr(ctx,'user_id',None):
            raise DomainError('UNAUTHORIZED','تسجيل الدخول مطلوب.',{})
        tenant_id = getattr(ctx, 'tenant_id', None)
        if not tenant_id:
            raise DomainError('TENANT_REQUIRED','هوية المستأجر مطلوبة.',{})
        set_tenant_scope(str(tenant_id))
        self._active_tenant = str(tenant_id)
        if perm not in getattr(ctx,'permissions',frozenset()):
            raise DomainError('FORBIDDEN','لا توجد صلاحية لتنفيذ العملية.',{'permission':perm})
        # A locked closing freezes operational commands for the closed business day.
        # Re-opening is an explicit privileged operation; closing itself handles the
        # duplicate-close case separately.
        if perm not in {'closing.reopen','closing.close'}:
            today=date.today()
            if any(
                c.branch_id==ctx.branch_id and c.locked and c.closing_date<=today
                for c in self.closings.all()
            ):
                raise DomainError('DAY_CLOSED','تم إغلاق اليوم لهذا الفرع.',{'branch_id':ctx.branch_id})
    def _idem(self, ctx):
        return self._processed.get(ctx.idempotency_key)
    def _audit(self,ctx,action,ref,details=None):
        self.audit.create(f'{ctx.idempotency_key}:audit',{'command_id':ctx.command_id,'user_id':ctx.user_id,'tenant_id':ctx.tenant_id,'branch_id':ctx.branch_id,'action':action,'reference_id':ref,'details':details or {}})
    def _wallet(self,wid,bid):
        w=self.wallets.get(wid)
        if not w: raise DomainError('NOT_FOUND','المحفظة غير موجودة.',{'wallet_id':wid})
        if w.branch_id!=bid: raise DomainError('BRANCH_ACCESS_DENIED','المحفظة خارج الفرع.',{})
        return w
    def _balance(self,wid):
        def val(e,k): return getattr(e,k,e.get(k,D0) if isinstance(e,dict) else D0)
        return sum((dec(val(e,'debit'))-dec(val(e,'credit')) for e in self.ledger.all() if val(e,'account_id')==f'wallet:{wid}'),D0)
    def _put(self,repo,obj):
        oid=obj.id if hasattr(obj,'id') else obj['id']
        repo.create(oid, obj, tenant_id=getattr(self, "_active_tenant", None))

    def create_purchase(self,command,supplier_id,items,paid=D0):
        with self._lock:
            self._auth(_ctx(command),'purchases.create'); old=self._idem(_ctx(command))
            if old:return old
            if not items: raise DomainError('INVALID_INPUT','المشتريات بدون أصناف.',{})
            total=sum((dec(i['quantity'])*dec(i['unit_cost']) for i in items),D0); paid=money(paid)
            if paid<0 or paid>total: raise DomainError('INVALID_PAYMENT','قيمة السداد غير صحيحة.',{})
            supplier = self.suppliers.get(supplier_id)
            if not supplier:
                raise DomainError('NOT_FOUND','المورد غير موجود.',{'supplier_id':supplier_id})
            if getattr(supplier, 'branch_ids', ()) and _ctx(command).branch_id not in supplier.branch_ids:
                raise DomainError('BRANCH_ACCESS_DENIED','المورد خارج الفروع المسموح بها.',{})
            wallet_id=next((i.get('wallet_id') for i in items if i.get('wallet_id')),None)
            if paid:
                if not wallet_id: raise DomainError('INVALID_PAYMENT','يجب تحديد محفظة للسداد.',{})
                self._wallet(wallet_id,_ctx(command).branch_id)
                if self._balance(wallet_id)<paid: raise DomainError('INSUFFICIENT_WALLET_BALANCE','رصيد المحفظة غير كافٍ.',{})
            pis=[]; unit_updates=[]
            for n,i in enumerate(items):
                q=dec(i['quantity']); cost=dec(i['unit_cost'])
                if q<=0 or cost<0: raise DomainError('INVALID_INPUT','الكمية والتكلفة غير صحيحتين.',{})
                uid=i.get('product_unit_id')
                if uid:
                    u=self.units.get(uid)
                    if not u: raise DomainError('NOT_FOUND','وحدة المنتج غير موجودة.',{})
                    if u.branch_id!=_ctx(command).branch_id: raise DomainError('BRANCH_ACCESS_DENIED','الوحدة خارج الفرع.',{})
                    if u.status=='SOLD': raise DomainError('INVALID_INPUT','الوحدة مباعة بالفعل.',{})
                    unit_updates.append((u,i,cost))
                elif not self.products.get(i['product_id']): raise DomainError('NOT_FOUND','المنتج غير موجود.',{})
                pis.append(PurchaseItem(f'{_ctx(command).command_id}:{n}',i['product_id'],q,cost,uid))
            p=Purchase(_ctx(command).command_id,_ctx(command).branch_id,supplier_id,tuple(pis),total,paid)
            self._put(self.purchases,p)
            for u,i,cost in unit_updates:
                nu=replace(u,status='AVAILABLE',purchase_cost=cost,final_cost=money(cost+u.refurbishing_cost+u.direct_cost))
                self.units.update(u.id,nu); self._put(self.stock,StockMovement(f'{p.id}:{u.id}',p.branch_id,i['product_id'],D0,'PURCHASE',p.id,u.id,nu.final_cost))
            self._put(self.ledger,LedgerEntry(f'{p.id}:inventory',p.branch_id,'inventory','PURCHASE',debit=total,reference_id=p.id))
            if paid:self._put(self.ledger,LedgerEntry(f'{p.id}:wallet',p.branch_id,f'wallet:{wallet_id}','PURCHASE_PAYMENT',credit=paid,reference_id=p.id))
            self._audit(_ctx(command),'CREATE_PURCHASE',p.id,{'total':str(total),'paid':str(paid)}); self._processed[_ctx(command).idempotency_key]=p; return p

    def _available_qty(self,bid,pid):
        return sum((m.quantity for m in self.stock.all() if m.branch_id==bid and m.product_id==pid and not m.unit_id),D0)
    def _avg_cost(self,bid,pid):
        prod=self.products.get(pid)
        movements=[m for m in self.stock.all() if m.branch_id==bid and m.product_id==pid and not m.unit_id]
        qty=sum((m.quantity for m in movements),D0); value=sum((m.quantity*m.cost for m in movements),D0)
        return (value/qty if qty else (prod.default_cost if prod else D0))

    def create_sale(self,command):
        with self._lock:
            self._auth(_ctx(command),'sales.create'); old=self._idem(_ctx(command))
            if old:return old
            if not command.items: raise DomainError('INVALID_INPUT','الفاتورة بدون أصناف.',{})
            if command.customer_id is not None and not self.customers.get(command.customer_id):
                raise DomainError('NOT_FOUND','العميل غير موجود.',{'customer_id':command.customer_id})
            discount=money(command.discount); items=[]; subtotal=D0; cost_total=D0
            for n,r in enumerate(command.items):
                q=dec(r.get('quantity',1)); price=money(r['unit_price'])
                if q<=0 or price<0: raise DomainError('INVALID_INPUT','الكمية والسعر غير صحيحين.',{})
                uid=r.get('product_unit_id'); cost=D0
                if uid:
                    u=self.units.get(uid)
                    if not u: raise DomainError('NOT_FOUND','وحدة المنتج غير موجودة.',{})
                    if u.branch_id!=_ctx(command).branch_id: raise DomainError('BRANCH_ACCESS_DENIED','الوحدة خارج الفرع.',{})
                    if u.status=='SOLD': raise DomainError('IMEI_ALREADY_SOLD','هذا الـIMEI تم بيعه بالفعل.',{})
                    if u.status!='AVAILABLE': raise DomainError('INVALID_INPUT','الوحدة غير متاحة للبيع.',{})
                    cost=u.final_cost
                else:
                    if not self.products.get(r['product_id']): raise DomainError('NOT_FOUND','المنتج غير موجود.',{})
                    if self._available_qty(_ctx(command).branch_id,r['product_id'])<q: raise DomainError('INSUFFICIENT_STOCK','المخزون غير كافٍ.',{})
                    cost=self._avg_cost(_ctx(command).branch_id,r['product_id'])
                line=q*price; subtotal+=line; cost_total+=q*cost
                items.append(SaleItem(f'{_ctx(command).command_id}:{n}',r['product_id'],q,price,cost,uid))
            total=money(subtotal-discount)
            if total<0: raise DomainError('INVALID_INPUT','الخصم أكبر من قيمة الفاتورة.',{})
            pays=tuple(Payment(f'{_ctx(command).command_id}:pay:{n}',_ctx(command).command_id,p['wallet_id'],money(p['amount'])) for n,p in enumerate(command.payments))
            if sum((p.amount for p in pays),D0)!=total: raise DomainError('INVALID_PAYMENT','إجمالي المدفوعات لا يساوي إجمالي الفاتورة.',{})
            for p in pays:self._wallet(p.wallet_id,_ctx(command).branch_id)
            s=Sale(_ctx(command).command_id,_ctx(command).branch_id,command.customer_id,tuple(items),money(subtotal),discount,total,pays)
            self._put(self.sales,s)
            for i in items:
                if i.product_unit_id:self.units.update(i.product_unit_id,replace(self.units.get(i.product_unit_id),status='SOLD'))
                self._put(self.stock,StockMovement(f'{s.id}:out:{i.id}',s.branch_id,i.product_id,-i.quantity,'SALE',s.id,i.product_unit_id,i.cost_snapshot))
            # Sale accounting is double-entry: revenue/payment and COGS/inventory
            # are separate balanced legs of the same transaction.
            self._put(self.ledger,LedgerEntry(f'{s.id}:revenue',s.branch_id,'sales_revenue','SALE',credit=total,reference_id=s.id))
            for p in pays:self._put(self.ledger,LedgerEntry(p.id,s.branch_id,f'wallet:{p.wallet_id}','SALE_PAYMENT',debit=p.amount,reference_id=s.id))
            receivable=money(total-sum((p.amount for p in pays),D0))
            if receivable and s.customer_id:
                self._put(self.ledger,LedgerEntry(f'{s.id}:customer',s.branch_id,f'customer:{s.customer_id}','SALE_CREDIT',debit=receivable,reference_id=s.id))
            if cost_total:
                self._put(self.ledger,LedgerEntry(f'{s.id}:cogs',s.branch_id,'cost_of_goods_sold','SALE',debit=cost_total,reference_id=s.id))
                self._put(self.ledger,LedgerEntry(f'{s.id}:inventory',s.branch_id,'inventory','SALE',credit=cost_total,reference_id=s.id))
            self._audit(_ctx(command),'CREATE_SALE',s.id,{'total':str(total),'discount':str(discount)}); self._processed[_ctx(command).idempotency_key]=s; return s

    def void_sale(self,command,sale_id,reason=''):
        with self._lock:
            self._auth(_ctx(command),'sales.void'); old=self._idem(_ctx(command))
            if old:return old
            s=self.sales.get(sale_id)
            if not s: raise DomainError('NOT_FOUND','الفاتورة غير موجودة.',{})
            if s.branch_id!=_ctx(command).branch_id: raise DomainError('BRANCH_ACCESS_DENIED','الفاتورة خارج الفرع.',{})
            if s.status=='VOIDED': raise DomainError('SALE_ALREADY_VOIDED','الفاتورة ملغاة بالفعل.',{})
            # A void reverses the original wallet inflows. Validate every
            # refund wallet before mutating any state so a void cannot create
            # a negative cash/digital balance halfway through the operation.
            for payment in s.payments:
                if self._balance(payment.wallet_id) < payment.amount:
                    raise DomainError('INSUFFICIENT_WALLET_BALANCE','رصيد محفظة رد المبلغ غير كافٍ.',{'wallet_id':payment.wallet_id})
            ns=replace(s,status='VOIDED'); self.sales.update(s.id,ns)
            for i in s.items:
                self._put(self.stock,StockMovement(f'{s.id}:void:{i.id}',s.branch_id,i.product_id,i.quantity,'VOID_RETURN',s.id,i.product_unit_id,i.cost_snapshot))
                if i.product_unit_id:self.units.update(i.product_unit_id,replace(self.units.get(i.product_unit_id),status='AVAILABLE'))
            cogs=sum((i.quantity*i.cost_snapshot for i in s.items),D0)
            self._put(self.ledger,LedgerEntry(f'{s.id}:void:revenue',s.branch_id,'sales_revenue','SALE_VOID',debit=s.total,reference_id=s.id,reversal_of=f'{s.id}:revenue'))
            if cogs:
                self._put(self.ledger,LedgerEntry(f'{s.id}:void:cogs',s.branch_id,'cost_of_goods_sold','SALE_VOID',credit=cogs,reference_id=s.id,reversal_of=f'{s.id}:cogs'))
                self._put(self.ledger,LedgerEntry(f'{s.id}:void:inventory',s.branch_id,'inventory','SALE_VOID',debit=cogs,reference_id=s.id,reversal_of=f'{s.id}:inventory'))
            for p in s.payments:self._put(self.ledger,LedgerEntry(f'{s.id}:void:{p.id}',s.branch_id,f'wallet:{p.wallet_id}','SALE_REFUND',credit=p.amount,reference_id=s.id,reversal_of=p.id))
            receivable=s.total-sum((p.amount for p in s.payments),D0)
            if receivable:
                self._put(self.ledger,LedgerEntry(f'{s.id}:void:customer',s.branch_id,f'customer:{s.customer_id}','SALE_VOID',credit=receivable,reference_id=s.id,reversal_of=f'{s.id}:customer'))
            self._audit(_ctx(command),'VOID_SALE',s.id,{'reason':reason}); self._processed[_ctx(command).idempotency_key]=ns; return ns

    def return_sale(self,command,sale_id,items,refund_wallet_id=None):
        with self._lock:
            self._auth(_ctx(command),'sales.return'); old=self._idem(_ctx(command))
            if old:return old
            s=self.sales.get(sale_id)
            if not s:raise DomainError('NOT_FOUND','الفاتورة غير موجودة.',{})
            if s.branch_id!=_ctx(command).branch_id: raise DomainError('BRANCH_ACCESS_DENIED','الفاتورة خارج الفرع.',{})
            if s.status=='VOIDED':raise DomainError('INVALID_RETURN','لا يمكن إرجاع فاتورة ملغاة.',{})
            refund=D0; returned=[]
            for r in items:
                match=next((i for i in s.items if i.id==r.get('sale_item_id') or (i.product_id==r.get('product_id') and i.product_unit_id==r.get('product_unit_id'))),None)
                if not match:raise DomainError('INVALID_RETURN','الصنف غير موجود في الفاتورة.',{})
                q=dec(r.get('quantity',match.quantity));
                if q<=0 or q>match.quantity:raise DomainError('INVALID_RETURN','كمية المرتجع غير صحيحة.',{})
                refund += q*match.unit_price; returned.append((match,q))
            # Refunds must follow the original settlement method. A credit sale
            # cannot be turned into a cash payout, and a wallet cannot refund more
            # than it originally received for this sale.
            already = {}
            prior_wallet_refunds = D0
            for rr in self.returns.all():
                if isinstance(rr,dict) and rr.get('sale_id')==sale_id:
                    for item_id, qty in rr.get('items',()):
                        already[item_id]=already.get(item_id,D0)+dec(qty)
                    if refund_wallet_id and rr.get('refund_wallet_id')==refund_wallet_id:
                        prior_wallet_refunds += dec(rr.get('amount',D0))
            for match,q in returned:
                if already.get(match.id,D0)+q > match.quantity:
                    raise DomainError('INVALID_RETURN','تم تجاوز الكمية المتاحة للإرجاع.',{})
            if refund_wallet_id:
                self._wallet(refund_wallet_id,_ctx(command).branch_id)
                original_paid=sum((p.amount for p in s.payments if p.wallet_id==refund_wallet_id),D0)
                refundable=money(original_paid-prior_wallet_refunds)
                if money(refund)>refundable:
                    raise DomainError('INVALID_RETURN','قيمة المرتجع أكبر من المبلغ المدفوع من هذه المحفظة.',{})
                if self._balance(refund_wallet_id) < money(refund):
                    raise DomainError('INSUFFICIENT_WALLET_BALANCE','رصيد محفظة رد المبلغ غير كافٍ.',{})
            elif not s.customer_id:
                raise DomainError('INVALID_RETURN','المرتجع يحتاج محفظة رد أو عميل للفواتير الآجلة.',{})
            rid=_ctx(command).command_id; self._put(self.returns,{'id':rid,'sale_id':sale_id,'amount':money(refund),'items':tuple((i.id,q) for i,q in returned),'refund_wallet_id':refund_wallet_id})
            for i,q in returned:
                self._put(self.stock,StockMovement(f'{rid}:{i.id}',s.branch_id,i.product_id,q,'RETURN',sale_id,i.product_unit_id,i.cost_snapshot))
                if i.product_unit_id:self.units.update(i.product_unit_id,replace(self.units.get(i.product_unit_id),status='AVAILABLE'))
            refund_cost=sum((q*i.cost_snapshot for i,q in returned),D0)
            self._put(self.ledger,LedgerEntry(f'{rid}:revenue',s.branch_id,'sales_revenue','RETURN',debit=money(refund),reference_id=sale_id))
            if refund_cost:
                self._put(self.ledger,LedgerEntry(f'{rid}:cogs',s.branch_id,'cost_of_goods_sold','RETURN',credit=refund_cost,reference_id=sale_id,reversal_of=f'{sale_id}:cogs'))
                self._put(self.ledger,LedgerEntry(f'{rid}:inventory',s.branch_id,'inventory','RETURN',debit=refund_cost,reference_id=sale_id))
            if refund_wallet_id:self._put(self.ledger,LedgerEntry(f'{rid}:wallet',s.branch_id,f'wallet:{refund_wallet_id}','RETURN_REFUND',credit=money(refund),reference_id=sale_id))
            else:
                if s.customer_id:
                    self._put(self.ledger,LedgerEntry(f'{rid}:customer',s.branch_id,f'customer:{s.customer_id}','RETURN_RECEIVABLE',credit=money(refund),reference_id=sale_id))
            self._audit(_ctx(command),'RETURN_SALE',sale_id,{'amount':str(money(refund))}); self._processed[_ctx(command).idempotency_key]=self.returns.get(rid); return self.returns.get(rid)

    def create_expense(self,command,wallet_id,amount,category,note=None):
        with self._lock:
            self._auth(_ctx(command),'expenses.create'); old=self._idem(_ctx(command))
            if old:return old
            amount=money(amount); self._wallet(wallet_id,_ctx(command).branch_id)
            if amount<=0:raise DomainError('INVALID_INPUT','قيمة المصروف يجب أن تكون موجبة.',{})
            if self._balance(wallet_id)<amount:raise DomainError('INSUFFICIENT_WALLET_BALANCE','رصيد المحفظة غير كافٍ.',{})
            e=Expense(_ctx(command).command_id,_ctx(command).branch_id,wallet_id,amount,category,note=note); self._put(self.expenses,e)
            self._put(self.ledger,LedgerEntry(f'{e.id}:expense',e.branch_id,f'expense:{category}','EXPENSE',debit=amount,reference_id=e.id)); self._put(self.ledger,LedgerEntry(f'{e.id}:wallet',e.branch_id,f'wallet:{wallet_id}','EXPENSE_PAYMENT',credit=amount,reference_id=e.id))
            self._audit(_ctx(command),'CREATE_EXPENSE',e.id,{'amount':str(amount),'category':category}); self._processed[_ctx(command).idempotency_key]=e; return e

    def adjust_stock(self,command,product_id,quantity,cost=0,reason=''):
        with self._lock:
            self._auth(_ctx(command),'stock.adjust'); old=self._idem(_ctx(command))
            if old:return old
            q=dec(quantity); c=dec(cost)
            if not self.products.get(product_id):raise DomainError('NOT_FOUND','المنتج غير موجود.',{})
            if q==0:raise DomainError('INVALID_INPUT','التعديل لا يمكن أن يكون صفراً.',{})
            if q<0 and self._available_qty(_ctx(command).branch_id,product_id)+q<0:raise DomainError('INSUFFICIENT_STOCK','المخزون غير كافٍ.',{})
            m=StockMovement(_ctx(command).command_id,_ctx(command).branch_id,product_id,q,'ADJUSTMENT',_ctx(command).command_id,None,c)
            self._put(self.stock,m); self._audit(_ctx(command),'ADJUST_STOCK',m.id,{'quantity':str(q),'reason':reason}); self._processed[_ctx(command).idempotency_key]=m; return m

    def transfer_stock(self,command,product_id,quantity,from_branch,to_branch,cost=0):
        with self._lock:
            self._auth(_ctx(command),'stock.transfer'); old=self._idem(_ctx(command))
            if old:return old
            q=dec(quantity)
            if q<=0:raise DomainError('INVALID_INPUT','الكمية يجب أن تكون موجبة.',{})
            if from_branch!=_ctx(command).branch_id:raise DomainError('BRANCH_ACCESS_DENIED','الفرع المصدر غير مصرح.',{})
            if from_branch==to_branch:raise DomainError('INVALID_INPUT','لا يمكن تحويل المخزون إلى نفس الفرع.',{})
            if not self.products.get(product_id):raise DomainError('NOT_FOUND','المنتج غير موجود.',{'product_id':product_id})
            if not str(to_branch).strip():raise DomainError('INVALID_INPUT','الفرع المستلم غير صحيح.',{})
            if self._available_qty(from_branch,product_id)<q:raise DomainError('INSUFFICIENT_STOCK','المخزون غير كافٍ.',{})
            tid=_ctx(command).command_id; self._put(self.stock,StockMovement(f'{tid}:out',from_branch,product_id,-q,'TRANSFER_OUT',tid,None,dec(cost))); self._put(self.stock,StockMovement(f'{tid}:in',to_branch,product_id,q,'TRANSFER_IN',tid,None,dec(cost)))
            self._audit(_ctx(command),'TRANSFER_STOCK',tid,{'from':from_branch,'to':to_branch,'quantity':str(q)}); self._processed[_ctx(command).idempotency_key]=tid; return tid

    def transfer_between_wallets(self,command,source,destination,amount):
        with self._lock:
            self._auth(_ctx(command),'wallet.transfer'); old=self._idem(_ctx(command))
            if old:return old
            a=money(amount); s=self._wallet(source,_ctx(command).branch_id); d=self._wallet(destination,_ctx(command).branch_id)
            if source==destination or a<=0:raise DomainError('INVALID_INPUT','تحويل المحفظة غير صحيح.',{})
            comm=money(a*Decimal('0.01'))
            if self._balance(source)<a+comm:raise DomainError('INSUFFICIENT_WALLET_BALANCE','رصيد المحفظة المصدر غير كافٍ.',{})
            tid=_ctx(command).command_id
            # Internal wallet transfers are asset reclassifications. The 1% fee
            # reduces the source wallet and is booked as an expense so the journal
            # remains genuinely double-entry balanced.
            self._put(self.ledger,LedgerEntry(f'{tid}:out',_ctx(command).branch_id,f'wallet:{source}','WALLET_TRANSFER',credit=a+comm,reference_id=tid))
            self._put(self.ledger,LedgerEntry(f'{tid}:in',_ctx(command).branch_id,f'wallet:{destination}','WALLET_TRANSFER',debit=a,reference_id=tid))
            self._put(self.ledger,LedgerEntry(f'{tid}:commission',_ctx(command).branch_id,'transfer_commission_expense','TRANSFER_COMMISSION',debit=comm,reference_id=tid))
            self._audit(_ctx(command),'TRANSFER_WALLET',tid,{'amount':str(a),'commission':str(comm),'source':s.name,'destination':d.name}); self._processed[_ctx(command).idempotency_key]=tid; return tid

    def create_installment_plan(self,command,sale_id,customer_id,down_payment,rate_percent,term_months,rounding='0.01'):
        with self._lock:
            self._auth(_ctx(command),'installments.create'); old=self._idem(_ctx(command))
            if old:return old
            s=self.sales.get(sale_id)
            if not s:raise DomainError('NOT_FOUND','الفاتورة غير موجودة.',{})
            if s.branch_id!=_ctx(command).branch_id: raise DomainError('BRANCH_ACCESS_DENIED','الفاتورة خارج الفرع.',{})
            if s.customer_id!=customer_id: raise DomainError('INVALID_INPUT','العميل لا يطابق عميل الفاتورة.',{})
            if s.status=='VOIDED': raise DomainError('INVALID_INPUT','لا يمكن تقسيط فاتورة ملغاة.',{})
            if self.customers.get(customer_id) is None: raise DomainError('NOT_FOUND','العميل غير موجود.',{'customer_id':customer_id})
            paid=sum((p.amount for p in s.payments),D0)
            receivable=money(s.total-paid)
            down=money(down_payment); rate=dec(rate_percent); term=int(term_months)
            if down<0 or down>receivable or rate<0 or term<=0 or money(receivable-down)<=0:raise DomainError('INVALID_INSTALLMENT_TERM','شروط التقسيط غير صحيحة.',{})
            base=money(receivable-down); inc=money(base*rate/Decimal('100')); due=money(base+inc); monthly=(due/term).quantize(Decimal(str(rounding)),rounding=ROUND_HALF_UP)
            plan=InstallmentPlan(_ctx(command).command_id,sale_id,customer_id,base,rate,inc,due,term,monthly); self._put(self.installments,plan); self._audit(_ctx(command),'CREATE_INSTALLMENT',plan.id,{'total_due':str(due)}); self._processed[_ctx(command).idempotency_key]=plan; return plan

    def collect_installment(self,command,plan_id,amount,wallet_id):
        with self._lock:
            self._auth(_ctx(command),'installments.collect'); old=self._idem(_ctx(command))
            if old:return old
            p=self.installments.get(plan_id)
            if not p:raise DomainError('NOT_FOUND','خطة التقسيط غير موجودة.',{})
            a=money(amount); self._wallet(wallet_id,_ctx(command).branch_id)
            paid=sum((x.amount for x in self.installment_payments.all() if x.plan_id==plan_id),D0)
            if a<=0 or paid+a>p.total_due:raise DomainError('INVALID_PAYMENT','قيمة التحصيل تتجاوز المتبقي.',{})
            if p.customer_id and self.customers.get(p.customer_id) is None:
                raise DomainError('NOT_FOUND','العميل المرتبط بالتقسيط غير موجود.',{'customer_id':p.customer_id})
            # Allocate each payment to outstanding principal first, then financing interest.
            prior_paid=sum((x.amount for x in self.installment_payments.all() if x.plan_id==plan_id),D0)
            principal_paid=min(prior_paid,p.base_financed)
            interest_paid=max(D0,prior_paid-principal_paid)
            principal_part=min(a,max(D0,p.base_financed-principal_paid))
            interest_part=money(a-principal_part)
            ip=InstallmentPayment(_ctx(command).command_id,plan_id,a,wallet_id)
            self._put(self.installment_payments,ip)
            self._put(self.ledger,LedgerEntry(f'{ip.id}:wallet',_ctx(command).branch_id,f'wallet:{wallet_id}','INSTALLMENT_PAYMENT',debit=a,reference_id=plan_id))
            if p.customer_id and principal_part:
                self._put(self.ledger,LedgerEntry(f'{ip.id}:principal',_ctx(command).branch_id,f'customer:{p.customer_id}','INSTALLMENT_PRINCIPAL',credit=principal_part,reference_id=plan_id))
            if interest_part:
                self._put(self.ledger,LedgerEntry(f'{ip.id}:interest',_ctx(command).branch_id,'installment_interest','INSTALLMENT_INTEREST',credit=interest_part,reference_id=plan_id))
            self._audit(_ctx(command),'COLLECT_INSTALLMENT',plan_id,{'amount':str(a),'principal':str(principal_part),'interest':str(interest_part)}); self._processed[_ctx(command).idempotency_key]=ip; return ip

    def installment_remaining(self,plan_id):
        p=self.installments.get(plan_id)
        if not p:raise DomainError('NOT_FOUND','خطة التقسيط غير موجودة.',{})
        return money(p.total_due-sum((x.amount for x in self.installment_payments.all() if x.plan_id==plan_id),D0))

    _MAINT={'RECEIVED':'DIAGNOSING','DIAGNOSING':'WAITING_CUSTOMER','WAITING_CUSTOMER':'IN_PROGRESS','IN_PROGRESS':'READY','READY':'DELIVERED'}
    def create_maintenance_ticket(self,command,customer_id,device,problem,imei=None):
        with self._lock:
            self._auth(_ctx(command),'maintenance.create'); old=self._idem(_ctx(command))
            if old:return old
            customer = self.customers.get(customer_id)
            if not customer:
                raise DomainError('NOT_FOUND','العميل غير موجود.',{'customer_id':customer_id})
            t=MaintenanceTicket(_ctx(command).command_id,_ctx(command).branch_id,customer_id,device,imei,problem); self._put(self.maintenance,t); self._audit(_ctx(command),'CREATE_MAINTENANCE',t.id); self._processed[_ctx(command).idempotency_key]=t; return t
    def transition_maintenance(self,command,ticket_id,new_status):
        with self._lock:
            self._auth(_ctx(command),'maintenance.update'); old=self._idem(_ctx(command))
            if old:return old
            t=self.maintenance.get(ticket_id)
            if not t:raise DomainError('NOT_FOUND','طلب الصيانة غير موجود.',{})
            if t.branch_id!=_ctx(command).branch_id:raise DomainError('BRANCH_ACCESS_DENIED','طلب الصيانة خارج الفرع.',{})
            if new_status!=self._MAINT.get(t.status):raise DomainError('INVALID_INPUT','انتقال حالة الصيانة غير مسموح.',{'from':t.status,'to':new_status})
            nt=replace(t,status=new_status); self.maintenance.update(ticket_id,nt); self._audit(_ctx(command),'MAINTENANCE_STATUS',ticket_id,{'status':new_status}); self._processed[_ctx(command).idempotency_key]=nt; return nt
    def cancel_maintenance(self,command,ticket_id):
        with self._lock:
            self._auth(_ctx(command),'maintenance.update'); old=self._idem(_ctx(command))
            if old:return old
            t=self.maintenance.get(ticket_id)
            if not t:raise DomainError('NOT_FOUND','طلب الصيانة غير موجود.',{})
            if t.branch_id!=_ctx(command).branch_id:raise DomainError('BRANCH_ACCESS_DENIED','طلب الصيانة خارج الفرع.',{})
            if t.status in {'DELIVERED','CANCELLED'}:raise DomainError('INVALID_INPUT','لا يمكن إلغاء الطلب بعد إغلاقه.',{})
            nt=replace(t,status='CANCELLED'); self.maintenance.update(ticket_id,nt); self._audit(_ctx(command),'CANCEL_MAINTENANCE',ticket_id); self._processed[_ctx(command).idempotency_key]=nt; return nt
    def use_maintenance_part(self,command,ticket_id,product_id,quantity,cost):
        with self._lock:
            self._auth(_ctx(command),'maintenance.parts'); old=self._idem(_ctx(command))
            if old:return old
            q=dec(quantity); c=dec(cost); t=self.maintenance.get(ticket_id)
            if not t:raise DomainError('NOT_FOUND','طلب الصيانة غير موجود.',{})
            if self._available_qty(t.branch_id,product_id)<q:raise DomainError('INSUFFICIENT_STOCK','المخزون غير كافٍ.',{})
            part={'id':_ctx(command).command_id,'ticket_id':ticket_id,'product_id':product_id,'quantity':q,'cost':c}; self._put(self.maintenance_parts,part); self._put(self.stock,StockMovement(f'{part["id"]}:stock',t.branch_id,product_id,-q,'MAINTENANCE_USE',ticket_id,None,c)); nt=replace(t,parts_cost=t.parts_cost+q*c); self.maintenance.update(t.id,nt); self._audit(_ctx(command),'USE_MAINTENANCE_PART',ticket_id,{'product_id':product_id,'quantity':str(q)}); self._processed[_ctx(command).idempotency_key]=part; return part

    def reopen_day(self,command,closing_date):
        with self._lock:
            self._auth(_ctx(command),'closing.reopen')
            old=self._idem(_ctx(command))
            if old:return old
            rows=[c for c in self.closings.all() if c.branch_id==_ctx(command).branch_id and c.closing_date==closing_date and c.locked]
            if not rows:
                raise DomainError('NOT_FOUND','لا يوجد إقفال مغلق لهذا اليوم.',{})
            closing=rows[-1]
            reopened=replace(closing,locked=False)
            self.closings.update(closing.id,reopened)
            self._audit(_ctx(command),'REOPEN_DAY',closing.id,{'closing_date':str(closing_date)})
            self._processed[_ctx(command).idempotency_key]=reopened
            return reopened

    def close_day(self,command,closing_date,actual):
        with self._lock:
            self._auth(_ctx(command),'closing.close'); old=self._idem(_ctx(command))
            if old:return old
            if self.closings.all() and any(c.branch_id==_ctx(command).branch_id and c.closing_date==closing_date and c.locked for c in self.closings.all()):raise DomainError('INVALID_INPUT','اليوم مغلق بالفعل.',{})
            expected={}
            for w in self.wallets.all():
                if w.branch_id==_ctx(command).branch_id:expected[w.id]=self._balance(w.id)
            actual={k:money(v) for k,v in actual.items()}
            if any(v<0 for v in actual.values()) or any(k not in expected for k in actual):
                raise DomainError('INVALID_INPUT','أرصدة الإقفال الفعلية غير صحيحة.',{})
            discrepancy={k:money(actual.get(k,D0)-expected.get(k,D0)) for k in expected}
            c=DailyClosing(_ctx(command).command_id,_ctx(command).branch_id,closing_date,expected,actual,discrepancy,True); self._put(self.closings,c); self._audit(_ctx(command),'CLOSE_DAY',c.id,{'discrepancy':{k:str(v) for k,v in discrepancy.items()}}); self._processed[_ctx(command).idempotency_key]=c; return c


    def register_product_unit(self,command,unit):
        with self._lock:
            self._auth(_ctx(command),'inventory.create_unit'); old=self._idem(_ctx(command))
            if old:return old
            if unit.branch_id!=_ctx(command).branch_id: raise DomainError('BRANCH_ACCESS_DENIED','الوحدة خارج الفرع.',{})
            if not self.products.get(unit.product_id):
                raise DomainError('NOT_FOUND','المنتج غير موجود.',{'product_id':unit.product_id})
            identifiers=[x.strip() for x in (unit.imei1,unit.imei2,unit.serial_number) if x and str(x).strip()]
            if not identifiers:
                raise DomainError('INVALID_INPUT','يجب تسجيل IMEI أو Serial Number للوحدة.',{})
            if len(set(identifiers)) != len(identifiers):
                raise DomainError('IMEI_ALREADY_EXISTS','معرّفات الوحدة مكررة.',{})
            for u in self.units.all():
                existing=[x.strip() for x in (u.imei1,u.imei2,u.serial_number) if x and str(x).strip()]
                if set(identifiers) & set(existing):
                    raise DomainError('IMEI_ALREADY_EXISTS','الـIMEI أو Serial Number موجود بالفعل.',{})
            if unit.final_cost<0: raise DomainError('INVALID_INPUT','التكلفة غير صحيحة.',{})
            self._put(self.units,unit); self._audit(_ctx(command),'REGISTER_PRODUCT_UNIT',unit.id); self._processed[_ctx(command).idempotency_key]=unit; return unit

    def pay_supplier(self,command,supplier_id,wallet_id,amount,reference=None):
        with self._lock:
            self._auth(_ctx(command),'purchases.pay_supplier'); old=self._idem(_ctx(command))
            if old:return old
            a=money(amount); self._wallet(wallet_id,_ctx(command).branch_id)
            supplier=self.suppliers.get(supplier_id)
            if supplier is None: raise DomainError('NOT_FOUND','المورد غير موجود.',{'supplier_id':supplier_id})
            if getattr(supplier,'branch_ids',()) and _ctx(command).branch_id not in supplier.branch_ids:
                raise DomainError('BRANCH_ACCESS_DENIED','المورد غير متاح لهذا الفرع.',{})
            if a<=0 or self._balance(wallet_id)<a: raise DomainError('INSUFFICIENT_WALLET_BALANCE','رصيد المحفظة غير كافٍ.',{})
            if a>self.supplier_balance(supplier_id,_ctx(command).branch_id):
                raise DomainError('INVALID_PAYMENT','السداد أكبر من رصيد المورد.',{})
            obj={'id':_ctx(command).command_id,'supplier_id':supplier_id,'branch_id':_ctx(command).branch_id,'wallet_id':wallet_id,'amount':a,'reference':reference}
            self._put(self.catalog,obj); self._put(self.ledger,LedgerEntry(f'{obj["id"]}:pay',_ctx(command).branch_id,f'payable:{supplier_id}','SUPPLIER_PAYMENT',debit=a,reference_id=obj['id'])); self._put(self.ledger,LedgerEntry(f'{obj["id"]}:wallet',_ctx(command).branch_id,f'wallet:{wallet_id}','SUPPLIER_PAYMENT',credit=a,reference_id=obj['id'])); self._audit(_ctx(command),'PAY_SUPPLIER',obj['id'],{'amount':str(a)}); self._processed[_ctx(command).idempotency_key]=obj; return obj

    def adjust_wallet(self,command,wallet_id,amount,reason=''):
        with self._lock:
            self._auth(_ctx(command),'wallet.adjust'); old=self._idem(_ctx(command))
            if old:return old
            self._wallet(wallet_id,_ctx(command).branch_id); a=money(amount)
            if a==0: raise DomainError('INVALID_INPUT','التعديل لا يمكن أن يكون صفراً.',{})
            if a<0 and self._balance(wallet_id)+a<0: raise DomainError('INSUFFICIENT_WALLET_BALANCE','الرصيد لا يسمح بالتعديل.',{})
            typ='WALLET_ADJUST_IN' if a>0 else 'WALLET_ADJUST_OUT'; entry=LedgerEntry(_ctx(command).command_id,_ctx(command).branch_id,f'wallet:{wallet_id}',typ,debit=max(a,D0),credit=max(-a,D0),reference_id=_ctx(command).command_id)
            self._put(self.ledger,entry); self._audit(_ctx(command),'ADJUST_WALLET',entry.id,{'amount':str(a),'reason':reason}); self._processed[_ctx(command).idempotency_key]=entry; return entry

    def create_transfer(self,command,source_wallet,destination_wallet,amount,commission=None):
        with self._lock:
            self._auth(_ctx(command),'transfer.create'); old=self._idem(_ctx(command))
            if old:return old
            a=money(amount); s=self._wallet(source_wallet,_ctx(command).branch_id); d=self._wallet(destination_wallet,_ctx(command).branch_id)
            if a<=0 or self._balance(source_wallet)<a: raise DomainError('INSUFFICIENT_WALLET_BALANCE','الرصيد غير كافٍ.',{})
            comm=money(commission if commission is not None else a*Decimal('0.01'))
            if comm<0: raise DomainError('INVALID_INPUT','العمولة غير صحيحة.',{})
            tid=_ctx(command).command_id
            # Principal moves between wallets; only commission hits revenue.
            self._put(self.ledger,LedgerEntry(f'{tid}:principal-out',_ctx(command).branch_id,f'wallet:{source_wallet}','TRANSFER_PRINCIPAL',credit=a,reference_id=tid))
            self._put(self.ledger,LedgerEntry(f'{tid}:principal-in',_ctx(command).branch_id,f'wallet:{destination_wallet}','TRANSFER_PRINCIPAL',debit=a,reference_id=tid))
            if comm:self._put(self.ledger,LedgerEntry(f'{tid}:commission',_ctx(command).branch_id,'transfer_commission','TRANSFER_COMMISSION',credit=comm,reference_id=tid))
            obj={'id':tid,'source_wallet_id':source_wallet,'destination_wallet_id':destination_wallet,'amount':a,'commission':comm}; self._put(self.transfers,obj); self._audit(_ctx(command),'CREATE_TRANSFER',tid,{'amount':str(a),'commission':str(comm)}); self._processed[_ctx(command).idempotency_key]=obj; return obj

    def set_permission(self,command,user_id,permission,enabled=True):
        with self._lock:
            self._auth(_ctx(command),'permissions.change'); old=self._idem(_ctx(command))
            if old:return old
            current=self.settings.get(f'user:{user_id}:permissions') or {'id':f'user:{user_id}:permissions','permissions':set()}
            perms=set(current['permissions']); (perms.add(permission) if enabled else perms.discard(permission)); current['permissions']=frozenset(perms); self._put(self.settings,current); self._audit(_ctx(command),'CHANGE_PERMISSION',user_id,{'permission':permission,'enabled':enabled}); self._processed[_ctx(command).idempotency_key]=current; return current

    def set_setting(self,command,key,value):
        with self._lock:
            self._auth(_ctx(command),'settings.change'); old=self._idem(_ctx(command))
            if old:return old
            obj={'id':key,'value':value,'updated_by':_ctx(command).user_id,'branch_id':_ctx(command).branch_id}; self.settings.create(key,obj) if not self.settings.get(key) else self.settings.update(key,obj); self._audit(_ctx(command),'CHANGE_SETTING',key,{'value':value}); self._processed[_ctx(command).idempotency_key]=obj; return obj

    def calculate_salary(self,command,employee_id,period,base,commission=0,bonus=0,deductions=0):
        with self._lock:
            self._auth(_ctx(command),'employees.salary'); old=self._idem(_ctx(command))
            if old:return old
            e=self.employees.get(employee_id)
            if not e:raise DomainError('NOT_FOUND','الموظف غير موجود.',{})
            if getattr(e,'branch_ids',()) and _ctx(command).branch_id not in e.branch_ids: raise DomainError('BRANCH_ACCESS_DENIED','الموظف غير متاح لهذا الفرع.',{})
            vals=[money(x) for x in (base,commission,bonus,deductions)]
            if any(x<0 for x in vals):raise DomainError('INVALID_INPUT','قيم الراتب غير صحيحة.',{})
            rec=SalaryRecord(_ctx(command).command_id,employee_id,period,*vals,paid=D0); self._put(self.salary_records,rec); self._audit(_ctx(command),'CALCULATE_SALARY',rec.id,{'net':str(rec.base+rec.commission+rec.bonus-rec.deductions)}); self._processed[_ctx(command).idempotency_key]=rec; return rec

    def pay_salary(self,command,salary_id,wallet_id):
        with self._lock:
            self._auth(_ctx(command),'employees.salary'); old=self._idem(_ctx(command))
            if old:return old
            r=self.salary_records.get(salary_id)
            if not r:raise DomainError('NOT_FOUND','سجل الراتب غير موجود.',{})
            if r.paid>0: raise DomainError('INVALID_INPUT','الراتب تم صرفه بالفعل.',{})
            e=self.employees.get(r.employee_id)
            if e is None: raise DomainError('NOT_FOUND','الموظف غير موجود.',{})
            if getattr(e,'branch_ids',()) and _ctx(command).branch_id not in e.branch_ids: raise DomainError('BRANCH_ACCESS_DENIED','الموظف غير متاح لهذا الفرع.',{})
            a=money(r.base+r.commission+r.bonus-r.deductions)
            if a<0: raise DomainError('INVALID_INPUT','صافي الراتب غير صحيح.',{})
            self._wallet(wallet_id,_ctx(command).branch_id)
            if self._balance(wallet_id)<a:raise DomainError('INSUFFICIENT_WALLET_BALANCE','رصيد المحفظة غير كافٍ.',{})
            nr=replace(r,paid=a); self.salary_records.update(r.id,nr); self._put(self.ledger,LedgerEntry(f'{r.id}:salary',_ctx(command).branch_id,'salary_expense','SALARY',debit=a,reference_id=r.id)); self._put(self.ledger,LedgerEntry(f'{r.id}:wallet',_ctx(command).branch_id,f'wallet:{wallet_id}','SALARY_PAYMENT',credit=a,reference_id=r.id)); self._audit(_ctx(command),'PAY_SALARY',r.id,{'amount':str(a)}); self._processed[_ctx(command).idempotency_key]=nr; return nr

    def reports(self,branch_id,start=None,end=None):
        sales=[s for s in self.sales.all() if s.branch_id==branch_id and s.status!='VOIDED' and (not start or s.created_at.date()>=start) and (not end or s.created_at.date()<=end)]
        revenue=sum((s.total for s in sales),D0); cogs=sum((i.quantity*i.cost_snapshot for s in sales for i in s.items),D0)
        return {'sales_count':len(sales),'revenue':money(revenue),'cogs':money(cogs),'gross_profit':money(revenue-cogs),'wallet_balances':{w.id:money(self._balance(w.id)) for w in self.wallets.all() if w.branch_id==branch_id}}

    def inventory_report(self,branch_id):
        out=[]
        for p in self.products.all():
            q=self._available_qty(branch_id,p.id); units=[u for u in self.units.all() if u.branch_id==branch_id and u.product_id==p.id and u.status=='AVAILABLE']
            uq=Decimal(len(units)); total_qty=q+uq; cost=(sum((u.final_cost for u in units),D0)+q*self._avg_cost(branch_id,p.id))
            out.append({'product_id':p.id,'quantity':total_qty,'value':money(cost)})
        return out
# Install the completed production-reference extensions when imported directly.
try:
    from backend.functions.services.completion import install_completion as _install_completion
    ERPCommandEngine = _install_completion(ERPCommandEngine)
except ImportError as exc:
    raise RuntimeError('ERP completion layer failed to load') from exc
