import 'dart:math';
import '../inventory/inventory_models.dart';
import '../inventory/inventory_repository.dart';
import '../inventory/local_store.dart';
import '../sync/online_push.dart';
import '../wallets/wallet_models.dart';
import '../wallets/wallet_provider.dart';
import 'sale_models.dart';
import 'sale_repository.dart';

/// Persists sales to the same on-device SQLite database used for inventory
/// (see LocalStore), and drives stock down/up through [InventoryRepository]
/// rather than touching stock rows directly, so inventory's own validation
/// (no negative stock, version checks, outbox command) stays the single
/// source of truth for what a stock change means.
///
/// Known limitation (worth flagging rather than hiding, in the spirit of the
/// project's own status doc): stock is decremented per line with sequential
/// awaits, not inside one shared database transaction with the sale record.
/// For a single-device/single-user demo this is fine; the status doc's own
/// "Make all financial commands execute atomically" item is what closes this
/// gap properly once the server-side authoritative DB exists.
class SqliteSalesRepository implements SalesRepository {
  SqliteSalesRepository._(this._store, this._inventory);
  final LocalStore _store;
  final InventoryRepository _inventory;
  static const _entity = 'sale';

  static Future<SqliteSalesRepository> create(InventoryRepository inventory) async {
    final store = await LocalStore.open();
    final repo = SqliteSalesRepository._(store, inventory);
    await repo._migrateLegacyCostAtSale();
    return repo;
  }

  /// 1.4 migration: sales created before `cost_at_sale` existed have items
  /// with no cost snapshot at all. Their real historical cost was never
  /// recorded, so the best available fallback is the product's cost *right
  /// now* — the same approximation the reports screen used to make fresh on
  /// every load before 1.4. The difference is this runs once and writes the
  /// result back, so:
  ///  - it stops silently drifting every time the product's cost changes later
  ///    (the historical report for a past period should stay stable), and
  ///  - every item on disk ends up with an explicit `costIsEstimated` flag,
  ///    so reports can tell real snapshots from backfilled guesses instead of
  ///    treating the whole report as one uniform estimate.
  /// Sales that already have `cost_at_sale` on every item are left untouched.
  Future<void> _migrateLegacyCostAtSale() async {
    final rows = await _store.listRecords(entity: _entity);
    final products = await _inventory.listProducts();
    final costById = {for (final p in products) p.id: p.defaultCost};

    for (final row in rows) {
      final rawItems = (row.payload['items'] as List).cast<Map<String, dynamic>>();
      final needsMigration = rawItems.any((i) => i['cost_at_sale'] == null);
      if (!needsMigration) continue;

      final migratedItems = rawItems.map((i) {
        if (i['cost_at_sale'] != null) return i;
        return {
          ...i,
          'cost_at_sale': costById[i['product_id']] ?? 0.0,
          'cost_is_estimated': true,
        };
      }).toList();

      final saleId = row.payload['id'] as String;
      await _store.upsertRecord(
        entity: _entity,
        recordId: saleId,
        payload: {...row.payload, 'items': migratedItems},
        expectedVersion: row.version,
      );
    }
  }

  Map<String, dynamic> _itemToPayload(SaleItemRecord i) => {
        'product_id': i.productId,
        'product_name': i.productName,
        'quantity': i.quantity,
        'unit_price': i.unitPrice,
        'cost_at_sale': i.costAtSale,
        'cost_is_estimated': i.costIsEstimated,
      };

  /// [m] may come from a sale created before 1.4 added `cost_at_sale`, in
  /// which case the key is simply absent. [create] runs a one-time
  /// migration that backfills every such row, so by the time normal reads
  /// happen the key should always be there — but this stays defensive
  /// (defaults to 0 / estimated) in case a record is ever read before that
  /// migration has run.
  SaleItemRecord _itemFromPayload(Map<String, dynamic> m) => SaleItemRecord(
        productId: m['product_id'] as String,
        productName: m['product_name'] as String,
        quantity: m['quantity'] as int,
        unitPrice: (m['unit_price'] as num).toDouble(),
        costAtSale: (m['cost_at_sale'] as num?)?.toDouble() ?? 0,
        costIsEstimated: m['cost_is_estimated'] as bool? ?? true,
      );

  Map<String, dynamic> _paymentToPayload(PaymentEntry p) => {
        'method': p.method.wireValue,
        'amount': p.amount,
      };

  PaymentEntry _paymentFromPayload(Map<String, dynamic> m) => PaymentEntry(
        method: PaymentMethodX.fromWireValue(m['method'] as String),
        amount: (m['amount'] as num).toDouble(),
      );

  Map<String, dynamic> _toPayload(SaleRecord s) => {
        'id': s.id,
        'customer_id': s.customerId,
        'customer_name': s.customerName,
        'items': s.items.map(_itemToPayload).toList(),
        'subtotal': s.subtotal,
        'discount': s.discount,
        'total': s.total,
        'payments': s.payments.map(_paymentToPayload).toList(),
        'status': s.status,
        'created_at': s.createdAt.toIso8601String(),
      };

  SaleRecord _toSale(Map<String, dynamic> payload) => SaleRecord(
        id: payload['id'] as String,
        customerId: payload['customer_id'] as String?,
        customerName: payload['customer_name'] as String?,
        items: (payload['items'] as List).map((e) => _itemFromPayload(e as Map<String, dynamic>)).toList(),
        subtotal: (payload['subtotal'] as num).toDouble(),
        discount: (payload['discount'] as num).toDouble(),
        total: (payload['total'] as num).toDouble(),
        payments: (payload['payments'] as List).map((e) => _paymentFromPayload(e as Map<String, dynamic>)).toList(),
        status: payload['status'] as String,
        createdAt: DateTime.parse(payload['created_at'] as String),
      );

  @override
  Future<List<SaleRecord>> listRecentSales({int limit = 50}) async {
    final rows = await _store.listRecords(entity: _entity);
    final sales = rows.map((r) => _toSale(r.payload)).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return sales.take(limit).toList(growable: false);
  }

  @override
  Future<List<SaleRecord>> listSalesInRange({DateTime? from, DateTime? to}) async {
    final rows = await _store.listRecords(entity: _entity);
    final sales = rows.map((r) => _toSale(r.payload)).where((s) {
      if (from != null && s.createdAt.isBefore(from)) return false;
      if (to != null && !s.createdAt.isBefore(to)) return false;
      return true;
    }).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return sales;
  }

  @override
  Future<SaleRecord> createSale({
    required List<SaleItemRecord> items,
    required List<PaymentEntry> payments,
    String? customerId,
    String? customerName,
    double discount = 0,
  }) async {
    if (items.isEmpty) throw SalesException('الفاتورة بدون أصناف.');
    if (discount < 0) throw SalesException('الخصم لا يمكن أن يكون سالبًا.');

    final subtotal = items.fold<double>(0, (sum, i) => sum + i.lineTotal);
    final total = subtotal - discount;
    if (total < 0) throw SalesException('الخصم أكبر من إجمالي الفاتورة.');

    final paid = payments.fold<double>(0, (sum, p) => sum + p.amount);
    if ((paid - total).abs() > 0.01) {
      throw SalesException('إجمالي المدفوعات (${paid.toStringAsFixed(2)}) لا يساوي إجمالي الفاتورة (${total.toStringAsFixed(2)}).');
    }

    // Validate all lines have enough stock *before* touching anything, to
    // minimise the odds of a partial decrement on failure. This same lookup
    // also gives us each product's cost *right now*, which is exactly what
    // "cost at the moment of sale" means — so we snapshot it into the item
    // here rather than trusting whatever the caller happened to pass in.
    final currentProducts = await _inventory.listProducts();
    final costById = <String, double>{};
    for (final item in items) {
      final product = currentProducts.where((p) => p.id == item.productId).firstOrNull;
      if (product == null) throw SalesException('الصنف "${item.productName}" لم يعد موجودًا.');
      if (product.type.wireValue != 'SERVICE' && product.quantity < item.quantity) {
        throw SalesException('الكمية غير كافية لـ "${product.name}" — المتاح: ${product.quantity}.');
      }
      costById[item.productId] = product.defaultCost;
    }
    final itemsWithCost = [
      for (final item in items)
        SaleItemRecord(
          productId: item.productId,
          productName: item.productName,
          quantity: item.quantity,
          unitPrice: item.unitPrice,
          costAtSale: costById[item.productId]!,
        ),
    ];

    final saleId = _newId('sale');
    for (final item in itemsWithCost) {
      // Local stock only: the server's createSale already deducts stock itself.
      await _inventory.adjustStock(item.productId, -item.quantity, 'بيع فاتورة #$saleId', queueSync: false);
    }

    final sale = SaleRecord(
      id: saleId,
      customerId: customerId,
      customerName: customerName,
      items: itemsWithCost,
      subtotal: subtotal,
      discount: discount,
      total: total,
      payments: payments,
      status: 'COMPLETED',
      createdAt: DateTime.now(),
    );
    await _store.upsertRecord(entity: _entity, recordId: sale.id, payload: _toPayload(sale), expectedVersion: 0);
    // Reuses saleId as the command id (instead of a separately-generated
    // one) specifically so that, when the online push below succeeds, the
    // server's own Sale record ends up with this exact same id
    // (`create_sale` in erp_engine.py sets the new Sale's id to
    // `command.command_id`) — local and server agree on what this sale is
    // called from the moment it's created, which voidSale below (and any
    // future download-sync in 5.2) relies on.
    // The queued payload is the exact server shape (same one pushed below), so
    // an offline sale replays correctly later. It used to queue the local
    // shape (payments keyed by 'method'), which the server can't apply.
    final serverSalePayload = {
      'customer_id': customerId,
      'items': [
        for (final item in itemsWithCost)
          {'product_id': item.productId, 'quantity': item.quantity, 'unit_price': item.unitPrice},
      ],
      'payments': _serverPayments(payments),
      'discount': discount,
    };
    await _store.queueCommand(
      commandId: saleId,
      command: 'createSale',
      payload: serverSalePayload,
    );
    // 4.3: push straight to the server too, best effort, on top of the
    // outbox row just queued above (unchanged — still there for 5.1).
    // Server shape differs from the local one in two ways `_itemToPayload`/
    // `_paymentToPayload` don't need to care about: no `product_unit_id`
    // (the mobile app never sells IMEI-tracked units), and payments are
    // keyed by `wallet_id`, not by [PaymentMethod] — CREDIT payments
    // have no wallet on the server (see `_postWalletEntries` below, which
    // skips them for the same reason), so they're left out of what's sent;
    // if that drops the paid total below the invoice total, the server
    // treats the gap as a receivable exactly like a partial/credit sale —
    // and rejects it if there's no customer to owe it, same as locally.
    await pushCommandOnline(_store, saleId, 'createSale', serverSalePayload);
    await _postWalletEntries(sale.payments, WalletTxType.sale, 'فاتورة بيع #$saleId', reversed: false);
    return sale;
  }

  /// Payment lines the server can actually attribute to a wallet — mirrors
  /// the same CASH/WALLET-only filter [_postWalletEntries] already applies
  /// locally, reused here so the online push and the local wallet ledger
  /// never disagree about which payments "count" as wallet money.
  List<Map<String, dynamic>> _serverPayments(List<PaymentEntry> payments) => [
        for (final p in payments)
          if (serverWalletRefForMethod(p.method.wireValue) != null)
            {'wallet_id': serverWalletRefForMethod(p.method.wireValue)!, 'amount': p.amount},
      ];

  /// Cash/wallet/instapay payment lines move real money, so they post to
  /// the wallet ledger too (see wallets/wallet_repository.dart). Credit is
  /// a receivable, not money on hand — it has no wallet balance, so
  /// tryFromWireValue skips it.
  Future<void> _postWalletEntries(
    List<PaymentEntry> payments,
    WalletTxType type,
    String note, {
    required bool reversed,
  }) async {
    final wallets = await getWalletRepository();
    for (final p in payments) {
      final walletId = BuiltinWallets.tryFromWireValue(p.method.wireValue)?.id;
      if (walletId == null) continue;
      final signed = reversed ? -p.amount : p.amount;
      await wallets.postAuto(walletId: walletId, signedAmount: signed, type: type, note: note);
    }
  }

  @override
  Future<SaleRecord> voidSale(String saleId) async {
    final current = await _store.getRecord(entity: _entity, recordId: saleId);
    if (current == null) throw SalesException('الفاتورة غير موجودة.');
    final sale = _toSale(current.payload);
    if (sale.status == 'VOIDED') throw SalesException('الفاتورة ملغاة بالفعل.');

    for (final item in sale.items) {
      try {
        // Local stock only: the server's voidSale already restores stock itself.
        await _inventory.adjustStock(item.productId, item.quantity, 'إلغاء فاتورة #$saleId', queueSync: false);
      } on InventoryException {
        // Product may have been deleted since the sale — stock can't be
        // restored to something that no longer exists. Voiding still
        // proceeds so the invoice itself is correctly marked.
      }
    }

    final voided = sale.copyWith(status: 'VOIDED');
    await _store.upsertRecord(
      entity: _entity,
      recordId: saleId,
      payload: _toPayload(voided),
      expectedVersion: current.version,
    );
    final voidCmdId = _newId('cmd-void');
    await _store.queueCommand(
      commandId: voidCmdId,
      command: 'voidSale',
      payload: {'sale_id': saleId},
    );
    // Safe to push directly: [saleId] is what the server knows this sale
    // as too, since createSale above pushed it under that same id.
    await pushCommandOnline(_store, voidCmdId, 'voidSale', {'sale_id': saleId});
    await _postWalletEntries(sale.payments, WalletTxType.sale, 'إلغاء فاتورة #$saleId', reversed: true);
    return voided;
  }

  String _newId(String prefix) => '$prefix-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(999999)}';
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
