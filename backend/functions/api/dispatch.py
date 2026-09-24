from shared.contracts.errors import DomainError

# ---------------------------------------------------------------------------
# Built-in wallet aliases.
#
# The mobile app has no wallet ids of its own on the server: it refers to its
# built-in wallets by the fixed names 'wallet-cash' / 'wallet-wallet' /
# 'wallet-instapay' (older builds sent the payment-method names 'CASH' /
# 'WALLET' / 'INSTAPAY' instead, and builds from before Card was replaced by
# InstaPay sent 'wallet-card' / 'CARD' — kept here only so any command still
# queued offline on an old install replays correctly; new builds never send
# it). Ids must be unique per tenant, so a fixed id can't be the real wallet
# id in a multi-branch tenant. Instead the server resolves each alias to
# *the caller's own branch's* wallet of that type, creating it the first
# time it is needed (a plain default drawer/wallet/instapay account, no user
# input).
# ---------------------------------------------------------------------------
_WALLET_ALIASES = {
    'wallet-cash': ('CASH', 'الخزنة (الدرج)'), 'CASH': ('CASH', 'الخزنة (الدرج)'),
    'wallet-wallet': ('WALLET', 'المحفظة'), 'WALLET': ('WALLET', 'المحفظة'),
    'wallet-instapay': ('INSTAPAY', 'انستاباي'), 'INSTAPAY': ('INSTAPAY', 'انستاباي'),
    # Legacy only — see note above.
    'wallet-card': ('INSTAPAY', 'انستاباي'), 'CARD': ('INSTAPAY', 'انستاباي'),
}
# Payment methods that never touch a wallet (an on-account/credit sale is just a receivable).
_NON_WALLET_METHODS = {'CREDIT'}


def _resolve_wallet(engine, ctx, ref):
    """Map a built-in wallet alias to this branch's real wallet id, provisioning it if missing."""
    spec = _WALLET_ALIASES.get(ref) if isinstance(ref, str) else None
    if spec is None:
        return ref
    wallet_type, display_name = spec

    def _find_or_create():
        exact = engine.wallets.get(ref)
        if exact is not None and exact.branch_id == ctx.branch_id:
            return exact.id
        for w in engine.wallets.all():
            if w.branch_id == ctx.branch_id and str(w.wallet_type).upper() == wallet_type and w.active:
                return w.id
        from shared.models.erp import Wallet
        wallet = Wallet(id=f'{ctx.branch_id}:{wallet_type.lower()}', branch_id=ctx.branch_id,
                        name=display_name, wallet_type=wallet_type)
        engine._put(engine.wallets, wallet)
        return wallet.id

    return engine.transaction(_find_or_create)


def _normalize_payments(engine, ctx, payments):
    """Server-shaped payments ({'wallet_id', 'amount'}), accepting the legacy
    {'method', 'amount'} shape too. Credit lines are dropped (they are the receivable)."""
    out = []
    for p in payments or ():
        p = dict(p)
        if 'wallet_id' not in p:
            method = str(p.get('method', '')).upper()
            if method in _NON_WALLET_METHODS:
                continue
            p['wallet_id'] = method
        p.pop('method', None)
        p['wallet_id'] = _resolve_wallet(engine, ctx, p['wallet_id'])
        out.append(p)
    return out


# Stock changes the *old* mobile build queued as a separate adjustStock next to
# createSale / voidSale / useMaintenancePart. Those commands already move stock
# on the server, so replaying the extra one would apply the change twice.
import re as _re
_LEGACY_DERIVED_STOCK_REASON = _re.compile(r'^((بيع|إلغاء) فاتورة #sale-[\w-]+|استخدام في صيانة #\S+)$')


def dispatch(engine, command_name, command, **payload):
    name = command_name
    mapping={'createSale':'create_sale','returnSale':'return_sale','voidSale':'void_sale','createPurchase':'create_purchase','paySupplier':'pay_supplier','createExpense':'create_expense','createTransfer':'transfer_customer','transferBetweenWallets':'transfer_between_wallets','createInstallmentPlan':'create_installment_plan','collectInstallment':'collect_installment','createMaintenanceTicket':'create_maintenance_ticket','transitionMaintenance':'transition_maintenance','cancelMaintenance':'cancel_maintenance','useMaintenancePart':'use_maintenance_part','deliverMaintenanceTicket':'deliver_maintenance','adjustStock':'adjust_stock','transferStock':'transfer_stock','closeDay':'close_day','adjustWallet':'adjust_wallet','changePermission':'set_permission','collectCustomer':'collect_customer','createProduct':'create_product','updateProduct':'update_product','createCustomer':'create_customer','updateCustomer':'update_customer','createSupplier':'create_supplier','updateSupplier':'update_supplier','createWallet':'create_wallet','createBranch':'create_branch','createRole':'create_role','createUserProfile':'create_user_profile','updateUserAccess':'update_user_access'}
    fn=mapping.get(name)
    if not fn or not hasattr(engine,fn): raise DomainError('INVALID_INPUT','الأمر غير مدعوم.',{'command':name})
    if name == 'adjustStock' and _LEGACY_DERIVED_STOCK_REASON.match(str(payload.get('reason', ''))):
        return {'skipped': True, 'reason': 'LEGACY_DERIVED_STOCK_ADJUSTMENT'}
    if name == 'createSale':
        payload['payments'] = _normalize_payments(engine, command, payload.get('payments'))
    elif name in ('createExpense', 'collectInstallment', 'deliverMaintenanceTicket', 'adjustWallet') and payload.get('wallet_id'):
        payload['wallet_id'] = _resolve_wallet(engine, command, payload['wallet_id'])
    elif name == 'transferBetweenWallets':
        if payload.get('source'):
            payload['source'] = _resolve_wallet(engine, command, payload['source'])
        if payload.get('destination'):
            payload['destination'] = _resolve_wallet(engine, command, payload['destination'])
    elif name == 'createInstallmentPlan':
        # Older builds queued the local plan shape (extra keys, no down_payment);
        # keep only what the server understands.
        payload = {k: payload[k] for k in ('sale_id', 'customer_id', 'down_payment', 'rate_percent',
                                           'term_months', 'down_payment_wallet_id') if k in payload}
        payload.setdefault('down_payment', 0)
        if not payload.get('sale_id'):
            raise DomainError('INVALID_INPUT', 'خطة التقسيط تتطلب فاتورة مرتبطة.', {})
        if payload.get('down_payment_wallet_id'):
            payload['down_payment_wallet_id'] = _resolve_wallet(engine, command, payload['down_payment_wallet_id'])
    # Some commands have richer immutable contracts than a bare context.
    if name == 'createSale':
        from shared.contracts.commands import CreateSaleCommand
        command = CreateSaleCommand(command, payload.get('customer_id'), tuple(payload.get('items', ())), tuple(payload.get('payments', ())), payload.get('discount', 0))
        payload = {}
    elif name == 'collectInstallment':
        # engine.collect_installment(command, plan_id, amount, wallet_id) takes
        # a bare CommandContext (only `_ctx(command)` is used inside) plus plain
        # kwargs — unlike createSale, it does not consume a rich contract
        # object. Building CollectInstallmentCommand and then discarding
        # payload (as this branch previously did) left nothing for
        # collect_installment's required plan_id/amount/wallet_id arguments,
        # so every collectInstallment call raised TypeError before it could
        # even reach validation. Keep `command` as the plain context and pass
        # the fields through as payload instead.
        payload = {'plan_id': payload['installment_id'], 'amount': payload['amount'], 'wallet_id': payload['wallet_id']}
    elif name == 'createProduct':
        # create_product(self, command, product) needs an actual Product
        # dataclass, not a bare dict — this was previously unhandled here
        # (only exercised via direct Python calls in tests, never over the
        # HTTP boundary), so build it the same way createSale/collectInstallment
        # build their contracts above.
        from decimal import Decimal
        from shared.models.erp import Product
        data = payload.get('product', payload)
        # Honour the client-generated product id: offline clients queue follow-up
        # commands (e.g. the opening-stock adjustStock) that reference it, so the
        # server must store the product under that same id, not the command id.
        product = Product(
            id=data.get('id') or command.command_id, name=data['name'], sku=data['sku'], product_type=data['product_type'],
            barcode=data.get('barcode'), selling_price=Decimal(str(data.get('selling_price', 0))),
            default_cost=Decimal(str(data.get('default_cost', 0))), warranty_days=int(data.get('warranty_days', 0)),
            reorder_level=Decimal(str(data.get('reorder_level', 0))), active=bool(data.get('active', True)),
        )
        payload = {'product': product}
    elif name == 'createCustomer':
        from shared.models.erp import Customer
        data = payload.get('customer', payload)
        customer = Customer(id=data.get('id') or command.command_id, name=data['name'], phone=data.get('phone'), active=bool(data.get('active', True)))
        payload = {'customer': customer}
    elif name == 'createSupplier':
        from shared.models.erp import Supplier
        data = payload.get('supplier', payload)
        supplier = Supplier(
            id=data.get('id') or command.command_id, name=data['name'], phone=data.get('phone'),
            branch_ids=tuple(data.get('branch_ids', ())), active=bool(data.get('active', True)),
        )
        payload = {'supplier': supplier}
    elif name == 'createBranch':
        from shared.models.erp import Branch
        data = payload.get('branch', payload)
        payload = {'branch': Branch(id=command.command_id, name=data['name'], code=data['code'], active=bool(data.get('active', True)))}
    elif name == 'createRole':
        from shared.models.erp import ERPUserRole
        data = payload.get('role', payload)
        payload = {'role': ERPUserRole(id=command.command_id, name=data['name'], permissions=tuple(data.get('permissions', ())), active=bool(data.get('active', True)))}
    elif name == 'createUserProfile':
        from shared.models.erp import ERPUser
        data = payload.get('user', payload)
        payload = {'user': ERPUser(id=data['id'], name=data['name'], branch_ids=tuple(data.get('branch_ids', ())), role_id=data.get('role_id'), permissions=tuple(data.get('permissions', ())), active=bool(data.get('active', True)))}
    elif name == 'updateUserAccess':
        payload = {
            'user_id': payload['user_id'],
            'branch_ids': tuple(payload.get('branch_ids', ())),
            'role_id': payload.get('role_id'),
            'permissions': tuple(payload.get('permissions', ())),
        }
    elif name in ('updateCustomer', 'updateSupplier'):
        # Accept both the wrapped {'customer_id', 'changes': {...}} form and the
        # flat entity payload ({'id': ..., 'name': ..., 'phone': ...}) that the
        # mobile client sends.
        id_key = 'customer_id' if name == 'updateCustomer' else 'supplier_id'
        entity_id = payload.get(id_key) or payload.get('id')
        if 'changes' in payload:
            changes = dict(payload['changes'])
        else:
            changes = {k: payload[k] for k in ('name', 'phone', 'active') if k in payload}
        payload = {id_key: entity_id, **changes}
    elif name == 'createWallet':
        # branch_id defaults to the caller's own branch and, even if a
        # client explicitly supplies a different one, create_wallet() in
        # completion.py rejects it — payload branch claims are never
        # trusted on their own, same principle as everywhere else in this
        # boundary.
        from shared.models.erp import Wallet
        data = payload.get('wallet', payload)
        wallet = Wallet(
            id=command.command_id, branch_id=data.get('branch_id', command.branch_id),
            name=data['name'], wallet_type=data['wallet_type'], active=bool(data.get('active', True)),
        )
        payload = {'wallet': wallet}
    elif name == 'adjustStock':
        # Both clients (apps/admin_mobile and apps/desktop) send the field as
        # 'delta' — engine.adjust_stock(command, product_id, quantity, cost=0,
        # reason='') takes 'quantity'. With no special case here this fell
        # through to the generic `getattr(engine, fn)(command, **payload)`
        # call below and raised a bare TypeError (unexpected keyword argument
        # 'delta', missing required 'quantity') for every adjustStock command
        # — not a DomainError, so command_endpoint's `except DomainError`
        # doesn't catch it either; it surfaces as a raw 500. This is why
        # opening-quantity/stock-adjustment commands were never actually
        # applied server-side even after a successful-looking sync.
        # 'delta' is what both real clients send; a couple of existing tests
        # call dispatch() directly with 'quantity' (the engine's own param
        # name) instead, bypassing the client wire format — accept either.
        qty = payload['delta'] if 'delta' in payload else payload['quantity']
        payload = {
            'product_id': payload['product_id'],
            'quantity': qty,
            'cost': payload.get('cost', 0),
            'reason': payload.get('reason', ''),
        }
    elif name == 'updateProduct':
        # update_product(self, command, product_id, **changes) uses
        # dataclasses.replace(), so `changes` values must already be the
        # right domain types (Decimal for money fields) — plain JSON
        # numbers/strings aren't coerced automatically.
        from decimal import Decimal
        # The mobile client sends the whole product flat ({'id': ..., 'name': ...,
        # 'quantity': ...}), not the wrapped {'product_id', 'changes'} form.
        # Accept both. 'quantity' is deliberately NOT an editable field: stock is
        # derived from stock movements, never set directly.
        product_id = payload.get('product_id') or payload.get('id')
        if 'changes' in payload:
            changes = dict(payload['changes'])
        else:
            editable = ('name', 'sku', 'product_type', 'barcode', 'selling_price',
                        'default_cost', 'warranty_days', 'reorder_level', 'active')
            changes = {k: payload[k] for k in editable if k in payload}
        for money_field in ('selling_price', 'default_cost', 'reorder_level'):
            if money_field in changes:
                changes[money_field] = Decimal(str(changes[money_field]))
        payload = {'product_id': product_id, **changes}
    return engine.transaction(lambda:getattr(engine,fn)(command,**payload))
