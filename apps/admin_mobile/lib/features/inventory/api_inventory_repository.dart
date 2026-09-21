import 'inventory_models.dart';
import 'inventory_repository.dart';
import '../../core/api_client.dart';

/// Online-mode inventory repository — calls the real backend over HTTP.
/// Implements the same [InventoryRepository] interface so the UI doesn't change.
///
/// Mirrors apps/desktop/api_inventory_repo.py behavior:
/// - GET /query/products for reads
/// - createProduct / updateProduct / adjustStock commands for writes
class ApiInventoryRepository implements InventoryRepository {
  ApiInventoryRepository({required this.client});

  final ApiClient client;

  Product _toProduct(Map<String, dynamic> d) => Product(
        id: d['id'] as String,
        name: d['name'] as String,
        sku: d['sku'] as String,
        type: ProductType.values.firstWhere(
          (t) => t.wireValue == (d['product_type'] as String? ?? ''),
          orElse: () => ProductType.accessory,
        ),
        barcode: d['barcode'] as String?,
        sellingPrice: double.parse(d['selling_price'].toString()),
        defaultCost: double.parse(d['default_cost'].toString()),
        reorderLevel: int.parse((d['reorder_level'] ?? 0).toString()),
        quantity: int.parse((d['quantity'] ?? 0).toString()),
      );

  @override
  Future<List<Product>> listProducts({
    ProductType? type,
    String query = '',
  }) async {
    final raw = await client.query('products');
    final all = raw.map(_toProduct).toList();
    final q = query.trim().toLowerCase();
    return all.where((p) {
      if (type != null && p.type != type) return false;
      if (q.isEmpty) return true;
      return p.name.toLowerCase().contains(q) ||
          p.sku.toLowerCase().contains(q) ||
          (p.barcode?.toLowerCase().contains(q) ?? false);
    }).toList()
      ..sort((a, b) => a.name.compareTo(b.name));
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
    final data = await client.command(
      ApiClient.newCommandId('cmd-create'),
      'createProduct',
      {
        'product': {
          'name': name,
          'sku': sku,
          'product_type': type.wireValue,
          'barcode': (barcode?.isEmpty ?? true) ? null : barcode,
          'selling_price': sellingPrice,
          'default_cost': defaultCost,
          'reorder_level': reorderLevel,
        },
      },
    );
    var product = _toProduct({...data, 'quantity': 0});
    if (openingQuantity > 0) {
      await adjustStock(product.id, openingQuantity, 'رصيد افتتاحي');
      final refreshed = await listProducts();
      product = refreshed.firstWhere((p) => p.id == product.id,
          orElse: () => product);
    }
    return product;
  }

  @override
  Future<Product> updateProduct(Product product) async {
    await client.command(
      ApiClient.newCommandId('cmd-update'),
      'updateProduct',
      {
        'product_id': product.id,
        'changes': {
          'name': product.name,
          'sku': product.sku,
          'product_type': product.type.wireValue,
          'barcode': product.barcode,
          'selling_price': product.sellingPrice,
          'default_cost': product.defaultCost,
          'reorder_level': product.reorderLevel,
        },
      },
    );
    // Re-fetch to get server-authoritative quantity.
    final refreshed = await listProducts();
    return refreshed.firstWhere((p) => p.id == product.id,
        orElse: () => product);
  }

  @override
  Future<Product> adjustStock(
      String productId, int delta, String reason) async {
    if (reason.trim().isEmpty) {
      throw InventoryException('يجب إدخال سبب حركة المخزون.');
    }
    await client.command(
      ApiClient.newCommandId('cmd-stock'),
      'adjustStock',
      {
        'product_id': productId,
        'delta': delta,
        'reason': reason,
      },
    );
    final refreshed = await listProducts();
    return refreshed.firstWhere(
      (p) => p.id == productId,
      orElse: () => throw InventoryException('الصنف غير موجود.'),
    );
  }
}
