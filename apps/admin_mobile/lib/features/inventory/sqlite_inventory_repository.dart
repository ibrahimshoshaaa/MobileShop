import 'dart:math';
import 'inventory_models.dart';
import 'inventory_repository.dart';
import 'local_store.dart';
import '../sync/online_push.dart';

/// Persists products to the on-device SQLite database instead of memory.
/// Every mutation also queues a command in the local outbox (see
/// [LocalStore.queueCommand]) so that once the real sync protocol from the
/// status doc's "Offline-to-Online behavior" section exists, these queued
/// commands are exactly what it needs to replay against the server.
class SqliteInventoryRepository implements InventoryRepository {
  SqliteInventoryRepository._(this._store);
  final LocalStore _store;
  static const _entity = 'product';

  static Future<SqliteInventoryRepository> create() async {
    final store = await LocalStore.open();
    final repo = SqliteInventoryRepository._(store);
    await repo._seedIfEmpty();
    return repo;
  }

  Future<void> _seedIfEmpty() async {
    final existing = await _store.listRecords(entity: _entity);
    if (existing.isNotEmpty) return;
    for (final product in _seedProducts()) {
      await _store.upsertRecord(entity: _entity, recordId: product.id, payload: _toPayload(product), expectedVersion: 0);
    }
  }

  List<Product> _seedProducts() => const [
        Product(
          id: 'p1',
          name: 'iPhone 13 128GB',
          sku: 'PH-IP13-128',
          type: ProductType.phoneNew,
          barcode: '6901234567001',
          sellingPrice: 28000,
          defaultCost: 24500,
          reorderLevel: 3,
          quantity: 5,
        ),
        Product(
          id: 'p2',
          name: 'سامسونج A54 مستعمل',
          sku: 'PH-SA54-USED',
          type: ProductType.phoneUsed,
          barcode: '6901234567002',
          sellingPrice: 9500,
          defaultCost: 7800,
          reorderLevel: 2,
          quantity: 1,
        ),
        Product(
          id: 'p3',
          name: 'شاحن سريع 20 وات',
          sku: 'ACC-CHG-20W',
          type: ProductType.accessory,
          barcode: '6901234567003',
          sellingPrice: 350,
          defaultCost: 180,
          reorderLevel: 10,
          quantity: 4,
        ),
        Product(
          id: 'p4',
          name: 'شاشة آيفون 12',
          sku: 'SP-SCR-IP12',
          type: ProductType.sparePart,
          sellingPrice: 1200,
          defaultCost: 700,
          reorderLevel: 3,
          quantity: 6,
        ),
        Product(
          id: 'p5',
          name: 'صيانة عامة',
          sku: 'SVC-GEN',
          type: ProductType.service,
          sellingPrice: 150,
          defaultCost: 0,
          reorderLevel: 0,
          quantity: 0,
        ),
      ];

  Product _toProduct(Map<String, dynamic> payload) => Product(
        id: payload['id'] as String,
        name: payload['name'] as String,
        sku: payload['sku'] as String,
        type: ProductTypeX.fromWireValue(payload['product_type'] as String),
        barcode: payload['barcode'] as String?,
        sellingPrice: (payload['selling_price'] as num).toDouble(),
        defaultCost: (payload['default_cost'] as num).toDouble(),
        reorderLevel: payload['reorder_level'] as int,
        quantity: payload['quantity'] as int,
        active: (payload['active'] as bool?) ?? true,
      );

  // Keys match the snake_case fields of shared/models/erp.py Product so a
  // future sync layer can pass this payload straight through.
  Map<String, dynamic> _toPayload(Product p) => {
        'id': p.id,
        'name': p.name,
        'sku': p.sku,
        'product_type': p.type.wireValue,
        'barcode': p.barcode,
        'selling_price': p.sellingPrice,
        'default_cost': p.defaultCost,
        'reorder_level': p.reorderLevel,
        'quantity': p.quantity,
        'active': p.active,
      };

  @override
  Future<List<Product>> listProducts({ProductType? type, String query = ''}) async {
    final rows = await _store.listRecords(entity: _entity);
    final q = query.trim().toLowerCase();
    return rows.map((r) => _toProduct(r.payload)).where((p) {
      final matchesType = type == null || p.type == type;
      final matchesQuery = q.isEmpty ||
          p.name.toLowerCase().contains(q) ||
          p.sku.toLowerCase().contains(q) ||
          (p.barcode?.toLowerCase().contains(q) ?? false);
      return matchesType && matchesQuery;
    }).toList(growable: false);
  }

  @override
  Future<Product> addProduct({
    required String name,
    required String sku,
    required ProductType type,
    String? barcode,
    required double sellingPrice,
    required double defaultCost,
    required int reorderLevel,
    required int openingQuantity,
  }) async {
    final existing = await listProducts();
    if (existing.any((p) => p.sku.toLowerCase() == sku.toLowerCase())) {
      throw InventoryException('رمز الصنف (SKU) "$sku" مستخدم بالفعل.');
    }
    final cleanBarcode = (barcode == null || barcode.isEmpty) ? null : barcode;
    if (cleanBarcode != null && existing.any((p) => p.barcode == cleanBarcode)) {
      throw InventoryException('الباركود مستخدم بالفعل لصنف آخر.');
    }
    final product = Product(
      id: _newId('p'),
      name: name,
      sku: sku,
      type: type,
      barcode: cleanBarcode,
      sellingPrice: sellingPrice,
      defaultCost: defaultCost,
      reorderLevel: reorderLevel,
      quantity: openingQuantity,
    );
    await _store.upsertRecord(entity: _entity, recordId: product.id, payload: _toPayload(product), expectedVersion: 0);
    final createCmdId = _newId('cmd-create');
    await _store.queueCommand(
      commandId: createCmdId,
      command: 'createProduct',
      payload: _toPayload(product),
    );
    // Already saved locally above, so the product shows up immediately. Now
    // make one best-effort attempt to sync it right away (never throws; if
    // offline it just stays PENDING for the next sync).
    await pushCommandOnline(_store, createCmdId, 'createProduct', _toPayload(product));
    // The server has no "quantity" field on Product — it only computes stock
    // from real StockMovement rows (see erp_engine.py's _available_qty), and
    // createProduct's payload on the server side never reads a quantity
    // field at all. So an opening quantity here was previously silently
    // dropped: the product would sync fine, but its server-side quantity
    // stayed 0 forever. Queue the same adjustStock command the "تعديل
    // الرصيد" button already uses successfully, so the opening balance
    // becomes a real stock movement once this syncs.
    if (openingQuantity != 0) {
      final stockCmdId = _newId('cmd-stock');
      final stockPayload = {'product_id': product.id, 'delta': openingQuantity, 'reason': 'رصيد افتتاحي'};
      await _store.queueCommand(commandId: stockCmdId, command: 'adjustStock', payload: stockPayload);
      await pushCommandOnline(_store, stockCmdId, 'adjustStock', stockPayload);
    }
    return product;
  }

  @override
  Future<Product> updateProduct(Product product) async {
    final current = await _store.getRecord(entity: _entity, recordId: product.id);
    if (current == null) throw InventoryException('الصنف غير موجود.');
    final others = await listProducts();
    final clash = others.any((p) => p.id != product.id && p.sku.toLowerCase() == product.sku.toLowerCase());
    if (clash) throw InventoryException('رمز الصنف (SKU) مستخدم بالفعل لصنف آخر.');
    try {
      await _store.upsertRecord(
        entity: _entity,
        recordId: product.id,
        payload: _toPayload(product),
        expectedVersion: current.version,
      );
    } on StaleVersionException catch (e) {
      throw InventoryException(e.toString());
    }
    final updateCmdId = _newId('cmd-update');
    await _store.queueCommand(commandId: updateCmdId, command: 'updateProduct', payload: _toPayload(product));
    await pushCommandOnline(_store, updateCmdId, 'updateProduct', _toPayload(product));
    return product;
  }

  @override
  Future<Product> adjustStock(String productId, int delta, String reason, {bool queueSync = true}) async {
    if (reason.trim().isEmpty) throw InventoryException('يجب إدخال سبب حركة المخزون.');
    final current = await _store.getRecord(entity: _entity, recordId: productId);
    if (current == null) throw InventoryException('الصنف غير موجود.');
    final product = _toProduct(current.payload);
    final newQuantity = product.quantity + delta;
    if (newQuantity < 0) throw InventoryException('الكمية الناتجة سالبة — تحقق من الرصيد الحالي.');
    final updated = product.copyWith(quantity: newQuantity);
    try {
      await _store.upsertRecord(
        entity: _entity,
        recordId: productId,
        payload: _toPayload(updated),
        expectedVersion: current.version,
      );
    } on StaleVersionException catch (e) {
      throw InventoryException(e.toString());
    }
    if (queueSync) {
      final cmdId = _newId('cmd-stock');
      final stockPayload = {'product_id': productId, 'delta': delta, 'reason': reason};
      await _store.queueCommand(commandId: cmdId, command: 'adjustStock', payload: stockPayload);
      await pushCommandOnline(_store, cmdId, 'adjustStock', stockPayload);
    }
    return updated;
  }

  String _newId(String prefix) => '$prefix-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(999999)}';
}
