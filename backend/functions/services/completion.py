from __future__ import annotations
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from shared.models.erp import *
from shared.contracts.errors import DomainError
from backend.functions.repositories.generic import current_tenant, set_tenant_scope, reset_tenant_scope

D0=Decimal('0'); CENT=Decimal('0.01')
def M(v): return Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)

def install_completion(engine_cls):
    def _require(ctx, perm): engine_cls._auth(ctx, perm)
    def create_product(self, command, product):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'products.edit'); old=self._idem(ctx)
            if old:return old
            for p in self.products.all():
                if p.sku==product.sku or (product.barcode and p.barcode==product.barcode):
                    raise DomainError('DUPLICATE_PRODUCT','SKU أو Barcode مستخدم بالفعل.',{})
            self._put(self.products,product); self._audit(ctx,'CREATE_PRODUCT',product.id); self._processed[ctx.idempotency_key]=product; return product
    def update_product(self, command, product_id, **changes):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'products.edit'); old=self._idem(ctx)
            if old:return old
            p=self.products.get(product_id)
            if not p: raise DomainError('NOT_FOUND','المنتج غير موجود.',{})
            allowed_fields={'name','sku','product_type','barcode','selling_price','default_cost','warranty_days','reorder_level','active'}
            unknown=set(changes)-allowed_fields
            if unknown:
                raise DomainError('INVALID_INPUT','حقول المنتج غير مسموح بتعديلها.',{'fields':sorted(unknown)})
            if 'name' in changes and not str(changes['name']).strip():
                raise DomainError('INVALID_INPUT','اسم المنتج مطلوب.',{})
            if 'sku' in changes and not str(changes['sku']).strip():
                raise DomainError('INVALID_INPUT','SKU مطلوب.',{})
            if 'selling_price' in changes and M(changes['selling_price'])<0:
                raise DomainError('INVALID_INPUT','سعر البيع لا يمكن أن يكون سالباً.',{})
            if 'default_cost' in changes and M(changes['default_cost'])<0:
                raise DomainError('INVALID_INPUT','التكلفة لا يمكن أن تكون سالبة.',{})
            if 'reorder_level' in changes and M(changes['reorder_level'])<0:
                raise DomainError('INVALID_INPUT','حد إعادة الطلب لا يمكن أن يكون سالباً.',{})
            if 'warranty_days' in changes and int(changes['warranty_days'])<0:
                raise DomainError('INVALID_INPUT','مدة الضمان لا يمكن أن تكون سالبة.',{})
            for other in self.products.all():
                if other.id==product_id: continue
                if 'sku' in changes and other.sku==changes['sku']:
                    raise DomainError('DUPLICATE_PRODUCT','SKU مستخدم بالفعل.',{})
                if 'barcode' in changes and changes['barcode'] and other.barcode==changes['barcode']:
                    raise DomainError('DUPLICATE_PRODUCT','Barcode مستخدم بالفعل.',{})
            typed=dict(changes)
            for field in ('selling_price','default_cost','reorder_level'):
                if field in typed: typed[field]=M(typed[field])
            if 'warranty_days' in typed: typed['warranty_days']=int(typed['warranty_days'])
            np=replace(p,**typed); self.products.update(product_id,np); self._audit(ctx,'CHANGE_PRODUCT',product_id,{'changes':typed}); self._processed[ctx.idempotency_key]=np; return np
    def create_branch(self, command, branch):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'branches.manage'); old=self._idem(ctx)
            if old:return old
            if not branch.name.strip() or not branch.code.strip():
                raise DomainError('INVALID_INPUT','اسم وكود الفرع مطلوبان.',{})
            if any(b.code==branch.code for b in self.branches.all()):
                raise DomainError('DUPLICATE_BRANCH','كود الفرع مستخدم بالفعل.',{})
            self._put(self.branches,branch); self._audit(ctx,'CREATE_BRANCH',branch.id); self._processed[ctx.idempotency_key]=branch; return branch

    def create_role(self, command, role):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'roles.manage'); old=self._idem(ctx)
            if old:return old
            if not role.name.strip(): raise DomainError('INVALID_INPUT','اسم الدور مطلوب.',{})
            if any(r.name==role.name for r in self.roles.all()):
                raise DomainError('DUPLICATE_ROLE','اسم الدور مستخدم بالفعل.',{})
            self._put(self.roles,role); self._audit(ctx,'CREATE_ROLE',role.id); self._processed[ctx.idempotency_key]=role; return role

    def create_user_profile(self, command, user):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'users.manage'); old=self._idem(ctx)
            if old:return old
            if self.users.get(user.id): raise DomainError('DUPLICATE_USER','ملف المستخدم موجود بالفعل.',{})
            for bid in user.branch_ids:
                b=self.branches.get(bid)
                if not b: raise DomainError('NOT_FOUND','الفرع غير موجود.',{'branch_id':bid})
                if not b.active: raise DomainError('INVALID_INPUT','لا يمكن إسناد مستخدم لفرع غير مفعّل.',{'branch_id':bid})
            if user.role_id and not self.roles.get(user.role_id):
                raise DomainError('NOT_FOUND','الدور غير موجود.',{'role_id':user.role_id})
            self._put(self.users,user); self._audit(ctx,'CREATE_USER_PROFILE',user.id); self._processed[ctx.idempotency_key]=user; return user

    def update_user_access(self, command, user_id, branch_ids, role_id=None, permissions=()):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'users.manage'); old=self._idem(ctx)
            if old:return old
            user=self.users.get(user_id)
            if not user: raise DomainError('NOT_FOUND','المستخدم غير موجود.',{'user_id':user_id})
            branches=tuple(dict.fromkeys(branch_ids))
            for bid in branches:
                b=self.branches.get(bid)
                if not b: raise DomainError('NOT_FOUND','الفرع غير موجود.',{'branch_id':bid})
                if not b.active: raise DomainError('INVALID_INPUT','لا يمكن إسناد مستخدم لفرع غير مفعّل.',{'branch_id':bid})
            if role_id and not self.roles.get(role_id): raise DomainError('NOT_FOUND','الدور غير موجود.',{'role_id':role_id})
            np=replace(user,branch_ids=branches,role_id=role_id,permissions=tuple(sorted(set(permissions))))
            self.users.update(user_id,np); self._audit(ctx,'UPDATE_USER_ACCESS',user_id,{'branch_ids':branches,'role_id':role_id,'permissions':list(np.permissions)}); self._processed[ctx.idempotency_key]=np; return np

    def create_customer(self, command, customer):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'customers.edit'); old=self._idem(ctx)
            if old:return old
            self._put(self.customers,customer); self._audit(ctx,'CREATE_CUSTOMER',customer.id); self._processed[ctx.idempotency_key]=customer; return customer
    def create_supplier(self, command, supplier):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'suppliers.edit'); old=self._idem(ctx)
            if old:return old
            self._put(self.suppliers,supplier); self._audit(ctx,'CREATE_SUPPLIER',supplier.id); self._processed[ctx.idempotency_key]=supplier; return supplier
    def update_customer(self, command, customer_id, **changes):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'customers.edit'); old=self._idem(ctx)
            if old:return old
            customer=self.customers.get(customer_id)
            if not customer: raise DomainError('NOT_FOUND','العميل غير موجود.',{'customer_id':customer_id})
            if 'name' in changes and not str(changes['name']).strip():
                raise DomainError('INVALID_INPUT','اسم العميل مطلوب.',{})
            unknown=set(changes)-{'name','phone','active'}
            if unknown:
                raise DomainError('INVALID_INPUT','حقول العميل غير مسموح بتعديلها.',{'fields':sorted(unknown)})
            allowed=dict(changes)
            updated=replace(customer,**allowed)
            self.customers.update(customer_id,updated)
            self._audit(ctx,'UPDATE_CUSTOMER',customer_id,{'changes':allowed})
            self._processed[ctx.idempotency_key]=updated
            return updated
    def update_supplier(self, command, supplier_id, **changes):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'suppliers.edit'); old=self._idem(ctx)
            if old:return old
            supplier=self.suppliers.get(supplier_id)
            if not supplier: raise DomainError('NOT_FOUND','المورد غير موجود.',{'supplier_id':supplier_id})
            if supplier.branch_ids and ctx.branch_id not in supplier.branch_ids:
                raise DomainError('BRANCH_ACCESS_DENIED','المورد غير متاح لهذا الفرع.',{})
            if 'name' in changes and not str(changes['name']).strip():
                raise DomainError('INVALID_INPUT','اسم المورد مطلوب.',{})
            unknown=set(changes)-{'name','phone','active'}
            if unknown:
                raise DomainError('INVALID_INPUT','حقول المورد غير مسموح بتعديلها.',{'fields':sorted(unknown)})
            allowed=dict(changes)
            updated=replace(supplier,**allowed)
            self.suppliers.update(supplier_id,updated)
            self._audit(ctx,'UPDATE_SUPPLIER',supplier_id,{'changes':allowed})
            self._processed[ctx.idempotency_key]=updated
            return updated
    def create_wallet(self, command, wallet):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'wallets.edit'); old=self._idem(ctx)
            if old:return old
            if wallet.branch_id!=ctx.branch_id: raise DomainError('BRANCH_ACCESS_DENIED','لا يمكن إنشاء محفظة خارج الفرع.',{})
            for w in self.wallets.all():
                if w.branch_id==wallet.branch_id and w.name==wallet.name:
                    raise DomainError('DUPLICATE_WALLET','اسم المحفظة مستخدم بالفعل في هذا الفرع.',{})
            self._put(self.wallets,wallet); self._audit(ctx,'CREATE_WALLET',wallet.id); self._processed[ctx.idempotency_key]=wallet; return wallet
    def customer_balance(self, customer_id, branch_id=None):
        bal=D0
        for e in self.ledger.all():
            aid=e.account_id if hasattr(e,'account_id') else e.get('account_id')
            bid=e.branch_id if hasattr(e,'branch_id') else e.get('branch_id')
            if aid==f'customer:{customer_id}' and (branch_id is None or bid==branch_id): bal += M((e.debit if hasattr(e,'debit') else e.get('debit',0)))-M((e.credit if hasattr(e,'credit') else e.get('credit',0)))
        return M(bal)
    def supplier_balance(self, supplier_id, branch_id=None):
        bal=D0
        for e in self.ledger.all():
            aid=e.account_id if hasattr(e,'account_id') else e.get('account_id'); bid=e.branch_id if hasattr(e,'branch_id') else e.get('branch_id')
            if aid==f'payable:{supplier_id}' and (branch_id is None or bid==branch_id): bal += M((e.credit if hasattr(e,'credit') else e.get('credit',0)))-M((e.debit if hasattr(e,'debit') else e.get('debit',0)))
        return M(bal)
    def customer_statement(self, customer_id, branch_id=None):
        rows=[]
        for e in self.ledger.all():
            aid=e.account_id if hasattr(e,'account_id') else e.get('account_id'); bid=e.branch_id if hasattr(e,'branch_id') else e.get('branch_id')
            if aid==f'customer:{customer_id}' and (branch_id is None or bid==branch_id): rows.append(e)
        return rows
    def supplier_statement(self, supplier_id, branch_id=None):
        rows=[]
        for e in self.ledger.all():
            aid=e.account_id if hasattr(e,'account_id') else e.get('account_id'); bid=e.branch_id if hasattr(e,'branch_id') else e.get('branch_id')
            if aid==f'payable:{supplier_id}' and (branch_id is None or bid==branch_id): rows.append(e)
        return rows
    def create_installment_schedule(self, plan_id, start_date=None):
        plan=self.installments.get(plan_id)
        if not plan: raise DomainError('NOT_FOUND','خطة التقسيط غير موجودة.',{})
        start_date=start_date or date.today(); monthly=plan.monthly_amount
        rows=[]; running=D0
        for n in range(1,plan.term_months+1):
            amount=monthly if n<plan.term_months else M(plan.total_due-running)
            rows.append({'id':f'{plan.id}:schedule:{n}','plan_id':plan.id,'sequence':n,'due_date':start_date+timedelta(days=30*n),'amount':amount,'paid_amount':D0,'remaining':amount,'status':'PENDING'})
            running+=amount
        self.installment_schedules= getattr(self,'installment_schedules',None) or __import__('backend.functions.repositories.generic',fromlist=['Repository']).Repository()
        for r in rows:self._put(self.installment_schedules,r)
        return tuple(rows)
    def installment_status(self, plan_id, as_of=None):
        as_of=as_of or date.today(); sched=getattr(self,'installment_schedules',None)
        if not sched:return []
        out=[]
        for r in sched.all():
            if r['plan_id']!=plan_id: continue
            nr=dict(r)
            if nr['remaining']>0 and nr['due_date']<as_of:nr['status']='OVERDUE'
            elif nr['remaining']==0:nr['status']='PAID'
            elif nr['paid_amount']>0:nr['status']='PARTIALLY_PAID'
            out.append(nr)
        return out
    def exchange_sale(self, command, sale_id, return_items, new_items, payments=()):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'sales.return'); old=self._idem(ctx)
            if old:return old
            original=self.sales.get(sale_id)
            if original is None: raise DomainError('NOT_FOUND','الفاتورة غير موجودة.',{})
            refund_wallet_id=original.payments[0].wallet_id if original.payments else None
            ret=self.return_sale(replace(ctx,command_id=f'{ctx.command_id}:exchange-return'),sale_id,return_items,refund_wallet_id)
            # New sale uses a distinct deterministic child command.
            newctx=replace(ctx,command_id=f'{ctx.command_id}:exchange-sale')
            from shared.contracts.commands import CreateSaleCommand
            sale=self.create_sale(CreateSaleCommand(newctx, self.sales.get(sale_id).customer_id, tuple(new_items), tuple(payments), Decimal('0')))
            obj={'id':ctx.command_id,'type':'EXCHANGE','return_id':ret['id'],'new_sale_id':sale.id,'difference':M(sale.total-ret['amount'])}
            self._put(self.returns,{**obj,'id':f'{ctx.command_id}:exchange','exchange_id':ctx.command_id}); self._audit(ctx,'EXCHANGE_SALE',sale_id,{'new_sale_id':sale.id}); self._processed[ctx.idempotency_key]=obj; return obj
    def warranty_check(self, branch_id, imei, as_of=None):
        as_of=as_of or date.today()
        for u in self.units.all():
            if u.branch_id==branch_id and (u.imei1==imei or u.imei2==imei):
                return bool(u.warranty_end and as_of<=u.warranty_end and u.status in {'SOLD','AVAILABLE'}), u.warranty_end
        return False, None
    def deliver_maintenance(self, command, ticket_id, final_price, payment, wallet_id):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'maintenance.update'); old=self._idem(ctx)
            if old:return old
            t=self.maintenance.get(ticket_id)
            if not t:raise DomainError('NOT_FOUND','طلب الصيانة غير موجود.',{})
            if self.customers.get(t.customer_id) is None: raise DomainError('NOT_FOUND','العميل المرتبط بالصيانة غير موجود.',{})
            if t.status!='READY':raise DomainError('INVALID_INPUT','لا يمكن التسليم قبل READY.',{})
            price=M(final_price); pay=M(payment)
            if price<0 or pay<0 or pay>price:raise DomainError('INVALID_PAYMENT','قيمة الدفع غير صحيحة.',{})
            if pay:
                if not wallet_id:
                    raise DomainError('INVALID_PAYMENT','يجب تحديد محفظة للسداد.',{})
                self._wallet(wallet_id,ctx.branch_id)
            if pay and self._balance(wallet_id) < pay:
                raise DomainError('INSUFFICIENT_WALLET_BALANCE','رصيد المحفظة غير كافٍ.',{'wallet_id':wallet_id})
            nt=replace(t,status='DELIVERED',final_cost=price,payment=pay); self.maintenance.update(t.id,nt)
            if pay:self._put(self.ledger,LedgerEntry(f'{ticket_id}:wallet',ctx.branch_id,f'wallet:{wallet_id}','MAINTENANCE_PAYMENT',debit=pay,reference_id=ticket_id))
            receivable=M(price-pay)
            if price:
                self._put(self.ledger,LedgerEntry(f'{ticket_id}:revenue',ctx.branch_id,'maintenance_revenue','MAINTENANCE',credit=price,reference_id=ticket_id))
            if receivable and t.customer_id:
                self._put(self.ledger,LedgerEntry(f'{ticket_id}:receivable',ctx.branch_id,f'customer:{t.customer_id}','MAINTENANCE_RECEIVABLE',debit=receivable,reference_id=ticket_id))
            if t.parts_cost:
                self._put(self.ledger,LedgerEntry(f'{ticket_id}:parts',ctx.branch_id,'maintenance_cost','MAINTENANCE_COGS',debit=t.parts_cost,reference_id=ticket_id))
                self._put(self.ledger,LedgerEntry(f'{ticket_id}:inventory',ctx.branch_id,'inventory','MAINTENANCE_USE',credit=t.parts_cost,reference_id=ticket_id))
            self._audit(ctx,'DELIVER_MAINTENANCE',ticket_id,{'price':str(price),'payment':str(pay)}); self._processed[ctx.idempotency_key]=nt; return nt
    def reports_full(self, branch_id, start=None, end=None):
        base=self.reports(branch_id,start,end)
        def in_range(entry):
            created=getattr(entry,'created_at',None)
            day=created.date() if created is not None and hasattr(created,'date') else None
            return (start is None or day is None or day>=start) and (end is None or day is None or day<=end)
        def net_account(account_id):
            return M(sum((M(getattr(e,'credit',0))-M(getattr(e,'debit',0)) for e in self.ledger.all()
                          if getattr(e,'branch_id',None)==branch_id and getattr(e,'account_id',None)==account_id and in_range(e)), D0))
        maintenance_revenue=net_account('maintenance_revenue')
        maintenance_cost=-net_account('maintenance_cost')
        transfer_income=net_account('transfer_commission')
        transfer_expense=-net_account('transfer_commission_expense')
        expenses=M(sum((M(getattr(e,'debit',0))-M(getattr(e,'credit',0)) for e in self.ledger.all()
                         if getattr(e,'branch_id',None)==branch_id and str(getattr(e,'account_id','')).startswith('expense:') and in_range(e)), D0))
        customers={c.id:self.customer_balance(c.id,branch_id) for c in self.customers.all()}
        suppliers={s.id:self.supplier_balance(s.id,branch_id) for s in self.suppliers.all()}
        return {**base,'maintenance_revenue':maintenance_revenue,'maintenance_cost':maintenance_cost,
                'maintenance_profit':M(maintenance_revenue-maintenance_cost),
                'transfer_commission':M(transfer_income-transfer_expense),'expenses':expenses,
                'net_profit':M(base['gross_profit']+maintenance_revenue-maintenance_cost+transfer_income-transfer_expense-expenses),
                'customer_receivables':customers,'supplier_payables':suppliers,
                'overdue_installments':sum(1 for p in self.installments.all() if self.installment_status(p.id) and any(x['status']=='OVERDUE' for x in self.installment_status(p.id)))}

    engine_cls.create_product=create_product; engine_cls.update_product=update_product; engine_cls.create_customer=create_customer; engine_cls.create_supplier=create_supplier; engine_cls.update_customer=update_customer; engine_cls.update_supplier=update_supplier; engine_cls.create_wallet=create_wallet
    engine_cls.customer_balance=customer_balance; engine_cls.supplier_balance=supplier_balance; engine_cls.customer_statement=customer_statement; engine_cls.supplier_statement=supplier_statement
    engine_cls.create_installment_schedule=create_installment_schedule; engine_cls.installment_status=installment_status; engine_cls.exchange_sale=exchange_sale; engine_cls.warranty_check=warranty_check; engine_cls.deliver_maintenance=deliver_maintenance; engine_cls.reports_full=reports_full
    def create_purchase_complete(self,command,supplier_id,items,paid=D0):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'purchases.create'); old=self._idem(ctx)
            if old:return old
            if not items: raise DomainError('INVALID_INPUT','المشتريات بدون أصناف.',{})
            total=M(sum((Decimal(str(i['quantity']))*Decimal(str(i['unit_cost'])) for i in items),D0)); paid=M(paid)
            if paid<0 or paid>total: raise DomainError('INVALID_PAYMENT','قيمة السداد غير صحيحة.',{})
            supplier = self.suppliers.get(supplier_id)
            if supplier is None: raise DomainError('NOT_FOUND','المورد غير موجود.',{'supplier_id':supplier_id})
            if getattr(supplier, 'branch_ids', ()) and ctx.branch_id not in supplier.branch_ids:
                raise DomainError('BRANCH_ACCESS_DENIED','المورد غير متاح لهذا الفرع.',{})
            wallet_id=next((i.get('wallet_id') for i in items if i.get('wallet_id')),None)
            if paid:
                if not wallet_id: raise DomainError('INVALID_PAYMENT','يجب تحديد محفظة للسداد.',{})
                self._wallet(wallet_id,ctx.branch_id)
                if self._balance(wallet_id)<paid: raise DomainError('INSUFFICIENT_WALLET_BALANCE','رصيد المحفظة غير كافٍ.',{})
            pis=[]
            for n,i in enumerate(items):
                q=Decimal(str(i['quantity'])); cost=M(i['unit_cost'])
                if q<=0 or cost<0: raise DomainError('INVALID_INPUT','الكمية والتكلفة غير صحيحتين.',{})
                uid=i.get('product_unit_id')
                if uid:
                    if q != Decimal('1'): raise DomainError('INVALID_INPUT','شراء وحدة IMEI يجب أن يكون بكمية 1.',{})
                    u=self.units.get(uid)
                    if not u: raise DomainError('NOT_FOUND','وحدة المنتج غير موجودة.',{})
                    if u.branch_id!=ctx.branch_id: raise DomainError('BRANCH_ACCESS_DENIED','الوحدة خارج الفرع.',{})
                    if u.product_id!=i['product_id']:
                        raise DomainError('INVALID_INPUT','وحدة المنتج لا تطابق المنتج المحدد.',{})
                    if u.status=='SOLD': raise DomainError('INVALID_INPUT','الوحدة مباعة بالفعل.',{})
                    if u.status!='AVAILABLE': raise DomainError('INVALID_INPUT','الوحدة غير متاحة للشراء.',{})
                    nu=replace(u,status='AVAILABLE',purchase_cost=cost,final_cost=M(cost+u.refurbishing_cost+u.direct_cost))
                    self.units.update(uid,nu)
                    self._put(self.stock,StockMovement(f'{ctx.command_id}:unit:{uid}',ctx.branch_id,i['product_id'],D0,'PURCHASE',ctx.command_id,uid,nu.final_cost))
                else:
                    if not self.products.get(i['product_id']): raise DomainError('NOT_FOUND','المنتج غير موجود.',{})
                    self._put(self.stock,StockMovement(f'{ctx.command_id}:stock:{n}',ctx.branch_id,i['product_id'],q,'PURCHASE',ctx.command_id,None,cost))
                pis.append(PurchaseItem(f'{ctx.command_id}:{n}',i['product_id'],q,cost,uid))
            p=Purchase(ctx.command_id,ctx.branch_id,supplier_id,tuple(pis),total,paid)
            self._put(self.purchases,p)
            self._put(self.ledger,LedgerEntry(f'{p.id}:inventory',p.branch_id,'inventory','PURCHASE',debit=total,reference_id=p.id))
            payable=total-paid
            if total:self._put(self.ledger,LedgerEntry(f'{p.id}:payable',p.branch_id,f'payable:{supplier_id}','PURCHASE_PAYABLE',credit=total,reference_id=p.id))
            if paid:
                self._put(self.ledger,LedgerEntry(f'{p.id}:wallet',p.branch_id,f'wallet:{wallet_id}','PURCHASE_PAYMENT',credit=paid,reference_id=p.id)); self._put(self.ledger,LedgerEntry(f'{p.id}:payable-paid',p.branch_id,f'payable:{supplier_id}','SUPPLIER_PAYMENT',debit=paid,reference_id=p.id))
            self._audit(ctx,'CREATE_PURCHASE',p.id,{'total':str(total),'paid':str(paid)}); self._processed[ctx.idempotency_key]=p; return p
    def create_sale_complete(self,command):
        ctx=command.context
        with self._lock:
            self._auth(ctx,'sales.create'); old=self._idem(ctx)
            if old:return old
            if not command.items: raise DomainError('INVALID_INPUT','الفاتورة بدون أصناف.',{})
            discount=M(command.discount)
            if discount<0: raise DomainError('INVALID_INPUT','الخصم غير صحيح.',{})
            if discount and 'sales.discount' not in ctx.permissions: raise DomainError('FORBIDDEN','لا توجد صلاحية للخصم.',{})
            items=[]; subtotal=D0; cogs=D0
            for n,r in enumerate(command.items):
                q=Decimal(str(r.get('quantity',1))); price=M(r['unit_price']); uid=r.get('product_unit_id')
                if q<=0 or price<0: raise DomainError('INVALID_INPUT','الكمية والسعر غير صحيحين.',{})
                cost=D0
                if uid:
                    if q != Decimal('1'): raise DomainError('INVALID_INPUT','بيع وحدة IMEI يجب أن يكون بكمية 1.',{})
                    u=self.units.get(uid)
                    if not u: raise DomainError('NOT_FOUND','وحدة المنتج غير موجودة.',{})
                    if u.branch_id!=ctx.branch_id: raise DomainError('BRANCH_ACCESS_DENIED','الوحدة خارج الفرع.',{})
                    if u.product_id!=r['product_id']:
                        raise DomainError('INVALID_INPUT','وحدة المنتج لا تطابق المنتج المحدد.',{})
                    if u.status=='SOLD': raise DomainError('IMEI_ALREADY_SOLD','هذا الـIMEI تم بيعه بالفعل.',{})
                    if u.status!='AVAILABLE': raise DomainError('INVALID_INPUT','الوحدة غير متاحة للبيع.',{})
                    cost=u.final_cost
                else:
                    if not self.products.get(r['product_id']): raise DomainError('NOT_FOUND','المنتج غير موجود.',{})
                    if self._available_qty(ctx.branch_id,r['product_id'])<q: raise DomainError('INSUFFICIENT_STOCK','المخزون غير كافٍ.',{})
                    cost=self._avg_cost(ctx.branch_id,r['product_id'])
                subtotal+=q*price; cogs+=q*cost; items.append(SaleItem(f'{ctx.command_id}:{n}',r['product_id'],q,price,cost,uid))
            total=M(subtotal-discount)
            if total<0: raise DomainError('INVALID_INPUT','الخصم أكبر من قيمة الفاتورة.',{})
            pays=tuple(Payment(f'{ctx.command_id}:pay:{n}',ctx.command_id,p['wallet_id'],M(p['amount'])) for n,p in enumerate(command.payments))
            paid=sum((p.amount for p in pays),D0)
            if paid>total: raise DomainError('INVALID_PAYMENT','المدفوع أكبر من إجمالي الفاتورة.',{})
            if paid<total and not command.customer_id: raise DomainError('INVALID_PAYMENT','البيع الآجل يتطلب عميلًا.',{})
            if command.customer_id and self.customers.get(command.customer_id) is None:
                raise DomainError('NOT_FOUND','العميل غير موجود.',{'customer_id':command.customer_id})
            for p in pays:self._wallet(p.wallet_id,ctx.branch_id)
            s=Sale(ctx.command_id,ctx.branch_id,command.customer_id,tuple(items),M(subtotal),discount,total,pays)
            self._put(self.sales,s)
            for i in items:
                if i.product_unit_id:self.units.update(i.product_unit_id,replace(self.units.get(i.product_unit_id),status='SOLD'))
                self._put(self.stock,StockMovement(f'{s.id}:out:{i.id}',s.branch_id,i.product_id,-i.quantity,'SALE',s.id,i.product_unit_id,i.cost_snapshot))
            self._put(self.ledger,LedgerEntry(f'{s.id}:revenue',ctx.branch_id,'sales_revenue','SALE',credit=total,reference_id=s.id))
            for p in pays:self._put(self.ledger,LedgerEntry(p.id,ctx.branch_id,f'wallet:{p.wallet_id}','SALE_PAYMENT',debit=p.amount,reference_id=s.id))
            if cogs:
                self._put(self.ledger,LedgerEntry(f'{s.id}:cogs',ctx.branch_id,'cost_of_goods_sold','SALE',debit=cogs,reference_id=s.id))
                self._put(self.ledger,LedgerEntry(f'{s.id}:inventory',ctx.branch_id,'inventory','SALE',credit=cogs,reference_id=s.id))
            receivable=total-paid
            if receivable:self._put(self.ledger,LedgerEntry(f'{s.id}:customer',ctx.branch_id,f'customer:{command.customer_id}','CUSTOMER_RECEIVABLE',debit=receivable,reference_id=s.id))
            self._audit(ctx,'CREATE_SALE',s.id,{'total':str(total),'discount':str(discount),'paid':str(paid),'credit':str(receivable)}); self._processed[ctx.idempotency_key]=s; return s
    engine_cls.create_purchase=create_purchase_complete
    engine_cls.create_sale=create_sale_complete
    def transaction(self, fn):
        """Atomic in-memory transaction with request-scoped tenant cleanup."""
        with self._lock:
            repos=[v for v in self.__dict__.values() if hasattr(v,'_data')]
            snapshots=[dict(r._data) for r in repos]
            tenant_snapshots=[dict(r._tenant_by_id) for r in repos]
            processed=dict(self._processed)
            # Preserve the caller's request scope. The transaction wrapper
            # must never erase tenant context before the command's own _auth()
            # establishes/validates it.
            previous_scope = current_tenant()
            scope_token = set_tenant_scope(previous_scope)
            try:
                return fn()
            except Exception:
                for r,snap,tenant_snap in zip(repos,snapshots,tenant_snapshots):
                    r._data=snap
                    r._tenant_by_id=tenant_snap
                self._processed=processed
                raise
            finally:
                reset_tenant_scope(scope_token)
    def collect_customer(self,command,customer_id,wallet_id,amount,reference=None):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'customers.collect'); old=self._idem(ctx)
            if old:return old
            a=M(amount); self._wallet(wallet_id,ctx.branch_id)
            if self.customers.get(customer_id) is None: raise DomainError('NOT_FOUND','العميل غير موجود.',{'customer_id':customer_id})
            if a<=0:raise DomainError('INVALID_PAYMENT','قيمة التحصيل غير صحيحة.',{})
            bal=self.customer_balance(customer_id,ctx.branch_id)
            if a>bal:raise DomainError('INVALID_PAYMENT','التحصيل أكبر من رصيد العميل.',{})
            obj={'id':ctx.command_id,'customer_id':customer_id,'wallet_id':wallet_id,'amount':a,'reference':reference,'branch_id':ctx.branch_id}
            self._put(self.catalog,obj); self._put(self.ledger,LedgerEntry(f'{obj["id"]}:customer',ctx.branch_id,f'customer:{customer_id}','CUSTOMER_PAYMENT',credit=a,reference_id=obj['id'])); self._put(self.ledger,LedgerEntry(f'{obj["id"]}:wallet',ctx.branch_id,f'wallet:{wallet_id}','CUSTOMER_PAYMENT',debit=a,reference_id=obj['id'])); self._audit(ctx,'COLLECT_CUSTOMER',obj['id'],{'amount':str(a)}); self._processed[ctx.idempotency_key]=obj; return obj
    def transfer_customer(self,command,source_wallet,destination_wallet,amount,commission=None,reason=None):
        ctx=command.context if hasattr(command,'context') else command
        with self._lock:
            self._auth(ctx,'transfer.create'); old=self._idem(ctx)
            if old:return old
            a=M(amount)
            if a<=0: raise DomainError('INVALID_INPUT','المبلغ غير صحيح.',{})
            src=self._wallet(source_wallet,ctx.branch_id); dst=self._wallet(destination_wallet,ctx.branch_id)
            if source_wallet==destination_wallet: raise DomainError('INVALID_INPUT','المحفظتان يجب أن تكونا مختلفتين.',{})
            rate=self.settings.get('transfer_commission')
            raw=(rate.get('value') if isinstance(rate,dict) else rate) if rate is not None else '0.01'
            default=M(raw)
            if default>1: default=default/Decimal('100')
            actual=M(commission if commission is not None else a*default)
            if actual<0: raise DomainError('INVALID_INPUT','العمولة غير صحيحة.',{})
            if commission is not None and not ({'transfer.override_commission','transfer.create'} & set(ctx.permissions)):
                raise DomainError('FORBIDDEN','لا توجد صلاحية لتعديل عمولة التحويل.',{})

            # Customer transfer semantics:
            # cash -> digital: cash increases by principal+commission; digital decreases principal.
            # digital -> cash: digital increases principal; cash decreases principal+commission.
            # The commission is recognized as revenue so every transaction balances.
            src_type=str(src.wallet_type).upper(); dst_type=str(dst.wallet_type).upper()
            cash_types={'CASH'}
            if src_type in cash_types and dst_type not in cash_types:
                if self._balance(destination_wallet)<a: raise DomainError('INSUFFICIENT_WALLET_BALANCE','الرصيد الرقمي غير كافٍ.',{})
                self._put(self.ledger,LedgerEntry(f'{ctx.command_id}:source',ctx.branch_id,f'wallet:{source_wallet}','CUSTOMER_TRANSFER_IN',debit=a+actual,reference_id=ctx.command_id))
                self._put(self.ledger,LedgerEntry(f'{ctx.command_id}:destination',ctx.branch_id,f'wallet:{destination_wallet}','CUSTOMER_TRANSFER_OUT',credit=a,reference_id=ctx.command_id))
            elif src_type not in cash_types and dst_type in cash_types:
                if self._balance(source_wallet)<a: raise DomainError('INSUFFICIENT_WALLET_BALANCE','الرصيد الرقمي غير كافٍ.',{})
                self._put(self.ledger,LedgerEntry(f'{ctx.command_id}:source',ctx.branch_id,f'wallet:{source_wallet}','CUSTOMER_TRANSFER_IN',debit=a,reference_id=ctx.command_id))
                self._put(self.ledger,LedgerEntry(f'{ctx.command_id}:destination',ctx.branch_id,f'wallet:{destination_wallet}','CUSTOMER_TRANSFER_OUT',credit=a+actual,reference_id=ctx.command_id))
            else:
                raise DomainError('INVALID_INPUT','تحويل العميل يجب أن يكون بين محفظة نقدية ومحفظة رقمية.',{})
            if actual:
                commission_side = 'credit' if src_type in cash_types else 'debit'
                self._put(self.ledger,LedgerEntry(
                    f'{ctx.command_id}:commission',
                    ctx.branch_id,
                    'transfer_commission' if commission_side == 'credit' else 'transfer_commission_expense',
                    'TRANSFER_COMMISSION',
                    **{commission_side: actual},
                    reference_id=ctx.command_id,
                ))
            obj={'id':ctx.command_id,'type':'CUSTOMER_TRANSFER','source_wallet_id':source_wallet,'destination_wallet_id':destination_wallet,'amount':a,'default_commission':default,'commission':actual,'override':commission is not None,'override_reason':reason}
            self._put(self.transfers,obj); self._audit(ctx,'CREATE_CUSTOMER_TRANSFER',ctx.command_id,{'amount':str(a),'commission':str(actual),'override':commission is not None}); self._processed[ctx.idempotency_key]=obj; return obj
    def report_rows(self,branch_id):
        r=self.reports_full(branch_id); return [{'metric':k,'value':v} for k,v in r.items() if not isinstance(v,(dict,list))]
    def ledger_transaction_totals(self, reference_id, branch_id=None):
        debit=D0; credit=D0
        for entry in self.ledger.all():
            ref=getattr(entry,'reference_id',None) if not isinstance(entry,dict) else entry.get('reference_id')
            bid=getattr(entry,'branch_id',None) if not isinstance(entry,dict) else entry.get('branch_id')
            if ref==reference_id and (branch_id is None or bid==branch_id):
                debit += M(getattr(entry,'debit',D0) if not isinstance(entry,dict) else entry.get('debit',D0))
                credit += M(getattr(entry,'credit',D0) if not isinstance(entry,dict) else entry.get('credit',D0))
        return M(debit), M(credit)

    def assert_ledger_balanced(self, reference_id, branch_id=None):
        debit, credit = self.ledger_transaction_totals(reference_id, branch_id)
        if debit != credit:
            raise DomainError('LEDGER_OUT_OF_BALANCE','القيد المحاسبي غير متوازن.',{
                'reference_id': reference_id, 'debit': str(debit), 'credit': str(credit)
            })
        return True

    engine_cls.transaction=transaction; engine_cls.create_branch=create_branch; engine_cls.create_role=create_role; engine_cls.create_user_profile=create_user_profile; engine_cls.update_user_access=update_user_access; engine_cls.collect_customer=collect_customer; engine_cls.transfer_customer=transfer_customer; engine_cls.report_rows=report_rows
    engine_cls.ledger_transaction_totals=ledger_transaction_totals; engine_cls.assert_ledger_balanced=assert_ledger_balanced

    # Financial commands are executed inside the same snapshot/rollback boundary.
    # This prevents half-posted sales, returns, purchases, collections, or payroll
    # when a later validation/persistence step raises an exception.
    _atomic_names = (
        'create_purchase','create_sale','void_sale','return_sale','create_expense',
        'adjust_wallet','transfer_between_wallets','create_installment_plan',
        'collect_installment','pay_supplier','collect_customer','transfer_customer','exchange_sale',
        'deliver_maintenance','use_maintenance_part','cancel_maintenance','adjust_stock','transfer_stock',
        'calculate_salary','pay_salary','close_day','reopen_day'
    )
    for _name in _atomic_names:
        _original = getattr(engine_cls, _name, None)
        if _original is None or getattr(_original, '_financial_atomic', False):
            continue
        def _make_atomic(original, name):
            def _wrapped(self, *args, **kwargs):
                return self.transaction(lambda: original(self, *args, **kwargs))
            _wrapped.__name__ = name
            _wrapped.__doc__ = original.__doc__
            _wrapped._financial_atomic = True
            return _wrapped
        setattr(engine_cls, _name, _make_atomic(_original, _name))

    return engine_cls
