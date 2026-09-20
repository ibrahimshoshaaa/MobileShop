import 'dart:math';
import '../inventory/inventory_repository.dart';
import '../inventory/local_store.dart';
import 'sale_models.dart';

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
    return SqliteSalesRepository._(store, inventory);
  }

  Map<String, dynamic> _itemToPayload(SaleItemRecord i) => {
        'product_id': i.productId,
        'product_name': i.productName,
        'quantity': i.quantity,
        'unit_price': i.unitPrice,
      };

  SaleItemRecord _itemFromPayload(Map<String, dynamic> m) => SaleItemRecord(
        productId: m['product_id'] as String,
        productName: m['product_name'] as String,
        quantity: m['quantity'] as int,
        unitPrice: (m['unit_price'] as num).toDouble(),
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
    // minimise the odds of a partial decrement on failure.
    final currentProducts = await _inventory.listProducts();
    for (final item in items) {
      final product = currentProducts.where((p) => p.id == item.productId).firstOrNull;
      if (product == null) throw SalesException('الصنف "${item.productName}" لم يعد موجودًا.');
      if (product.type.wireValue != 'SERVICE' && product.quantity < item.quantity) {
        throw SalesException('الكمية غير كافية لـ "${product.name}" — المتاح: ${product.quantity}.');
      }
    }

    final saleId = _newId('sale');
    for (final item in items) {
      await _inventory.adjustStock(item.productId, -item.quantity, 'بيع فاتورة #$saleId');
    }

    final sale = SaleRecord(
      id: saleId,
      customerId: customerId,
      customerName: customerName,
      items: items,
      subtotal: subtotal,
      discount: discount,
      total: total,
      payments: payments,
      status: 'COMPLETED',
      createdAt: DateTime.now(),
    );
    await _store.upsertRecord(entity: _entity, recordId: sale.id, payload: _toPayload(sale), expectedVersion: 0);
    await _store.queueCommand(
      commandId: _newId('cmd-sale'),
      command: 'createSale',
      payload: {
        'customer_id': customerId,
        'customer_name': customerName,
        'items': items.map(_itemToPayload).toList(),
        'payments': payments.map(_paymentToPayload).toList(),
        'discount': discount,
      },
    );
    return sale;
  }

  @override
  Future<SaleRecord> voidSale(String saleId) async {
    final current = await _store.getRecord(entity: _entity, recordId: saleId);
    if (current == null) throw SalesException('الفاتورة غير موجودة.');
    final sale = _toSale(current.payload);
    if (sale.status == 'VOIDED') throw SalesException('الفاتورة ملغاة بالفعل.');

    for (final item in sale.items) {
      try {
        await _inventory.adjustStock(item.productId, item.quantity, 'إلغاء فاتورة #$saleId');
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
    await _store.queueCommand(
      commandId: _newId('cmd-void'),
      command: 'voidSale',
      payload: {'sale_id': saleId},
    );
    return voided;
  }

  String _newId(String prefix) => '$prefix-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(999999)}';
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
