from shared.contracts.errors import DomainError

def dispatch(engine, name, command, **payload):
    mapping={'createSale':'create_sale','returnSale':'return_sale','voidSale':'void_sale','createPurchase':'create_purchase','paySupplier':'pay_supplier','createExpense':'create_expense','createTransfer':'transfer_customer','transferBetweenWallets':'transfer_between_wallets','createInstallmentPlan':'create_installment_plan','collectInstallment':'collect_installment','createMaintenanceTicket':'create_maintenance_ticket','useMaintenancePart':'use_maintenance_part','deliverMaintenanceTicket':'deliver_maintenance','adjustStock':'adjust_stock','transferStock':'transfer_stock','closeDay':'close_day','adjustWallet':'adjust_wallet','changePermission':'set_permission','collectCustomer':'collect_customer','createProduct':'create_product','updateProduct':'update_product','createCustomer':'create_customer','createSupplier':'create_supplier','createWallet':'create_wallet'}
    fn=mapping.get(name)
    if not fn or not hasattr(engine,fn): raise DomainError('INVALID_INPUT','الأمر غير مدعوم.',{'command':name})
    # Some commands have richer immutable contracts than a bare context.
    if name == 'createSale':
        from shared.contracts.commands import CreateSaleCommand
        command = CreateSaleCommand(command, payload.get('customer_id'), tuple(payload.get('items', ())), tuple(payload.get('payments', ())), payload.get('discount', 0))
        payload = {}
    elif name == 'collectInstallment':
        from shared.contracts.commands import CollectInstallmentCommand
        command = CollectInstallmentCommand(command, payload['installment_id'], payload['amount'], payload['wallet_id'])
        payload = {}
    elif name == 'createProduct':
        # create_product(self, command, product) needs an actual Product
        # dataclass, not a bare dict — this was previously unhandled here
        # (only exercised via direct Python calls in tests, never over the
        # HTTP boundary), so build it the same way createSale/collectInstallment
        # build their contracts above.
        from decimal import Decimal
        from shared.models.erp import Product
        data = payload.get('product', payload)
        product = Product(
            id=command.command_id, name=data['name'], sku=data['sku'], product_type=data['product_type'],
            barcode=data.get('barcode'), selling_price=Decimal(str(data.get('selling_price', 0))),
            default_cost=Decimal(str(data.get('default_cost', 0))), warranty_days=int(data.get('warranty_days', 0)),
            reorder_level=Decimal(str(data.get('reorder_level', 0))), active=bool(data.get('active', True)),
        )
        payload = {'product': product}
    elif name == 'createCustomer':
        from shared.models.erp import Customer
        data = payload.get('customer', payload)
        customer = Customer(id=command.command_id, name=data['name'], phone=data.get('phone'), active=bool(data.get('active', True)))
        payload = {'customer': customer}
    elif name == 'createSupplier':
        from shared.models.erp import Supplier
        data = payload.get('supplier', payload)
        supplier = Supplier(
            id=command.command_id, name=data['name'], phone=data.get('phone'),
            branch_ids=tuple(data.get('branch_ids', ())), active=bool(data.get('active', True)),
        )
        payload = {'supplier': supplier}
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
    elif name == 'updateProduct':
        # update_product(self, command, product_id, **changes) uses
        # dataclasses.replace(), so `changes` values must already be the
        # right domain types (Decimal for money fields) — plain JSON
        # numbers/strings aren't coerced automatically. Requires the
        # wrapped {'changes': {...}} form (not a flat payload) because a
        # product rename would otherwise send a top-level 'name' key,
        # which collides with dispatch()'s own 'name' parameter exactly
        # like createProduct/createCustomer/createWallet already do.
        from decimal import Decimal
        changes = dict(payload.get('changes', {}))
        for money_field in ('selling_price', 'default_cost', 'reorder_level'):
            if money_field in changes:
                changes[money_field] = Decimal(str(changes[money_field]))
        payload = {'product_id': payload['product_id'], **changes}
    return engine.transaction(lambda:getattr(engine,fn)(command,**payload))
