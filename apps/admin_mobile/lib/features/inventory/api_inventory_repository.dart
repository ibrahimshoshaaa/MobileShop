import '../sync/api_client.dart';
import 'inventory_models.dart';
import 'inventory_repository.dart';

/// Server-backed [InventoryRepository] — 4.2 ("قراءة البيانات ... من
/// السيرفر"). [listProducts] calls `GET /query/products` via [ApiClient]
/// instead of the local SQLite table, so the catalog shown reflects the
/// server's stock (`quantity` is computed server-side from `StockMovement`
/// rows, same as `apps/desktop/api_inventory_repo.py`'s `list_products`).
///
/// Writing a product isn't part of 4.2 or 4.3 (the plan only lists Sales /
/// Expenses / Maintenance / Installments for online writes) — so
/// [addProduct]/[updateProduct]/[adjustStock] delegate to [_local] (the
/// existing offline SQLite repository) exactly as before. That keeps every
/// other repository that reads inventory through the ordinary
/// [InventoryRepository] interface working unchanged; only the product
/// *list* now comes from the server when there's an active session.
class ApiInventoryRepository implements InventoryRepository {
  ApiInventoryRepository(this._client, this._local);

  final ApiClient _client;
  final InventoryRepository _local;

  Product _fromJson(Map<String, dynamic> j) => Product(
        id: j['id'] as String,
        name: j['name'] as String,
        sku: j['sku'] as String,
        type: ProductTypeX.fromWireValue(j['product_type'] as String),
        barcode: j['barcode'] as String?,
        sellingPrice: double.tryParse('${j['selling_price']}') ?? 0,
        defaultCost: double.tryParse('${j['default_cost']}') ?? 0,
        reorderLevel: (double.tryParse('${j['reorder_level']}') ?? 0).round(),
        quantity: (double.tryParse('${j['quantity']}') ?? 0).round(),
        active: j['active'] as bool? ?? true,
      );

  @override
  Future<List<Product>> listProducts({ProductType? type, String query = ''}) async {
    final List<Map<String, dynamic>> raw;
    try {
      raw = await _client.getProducts(limit: 500);
    } on ApiException catch (e) {
      throw InventoryException(e.message);
    }
    final q = query.trim().toLowerCase();
    final products = raw.map(_fromJson).where((p) {
      if (type != null && p.type != type) return false;
      if (q.isEmpty) return true;
      return p.name.toLowerCase().contains(q) ||
          p.sku.toLowerCase().contains(q) ||
          (p.barcode?.toLowerCase().contains(q) ?? false);
    }).toList()
      ..sort((a, b) => a.name.compareTo(b.name));
    return products;
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
  }) =>
      _local.addProduct(
        name: name,
        sku: sku,
        type: type,
        barcode: barcode,
        sellingPrice: sellingPrice,
        defaultCost: defaultCost,
        reorderLevel: reorderLevel,
        openingQuantity: openingQuantity,
      );

  @override
  Future<Product> updateProduct(Product product) => _local.updateProduct(product);

  @override
  Future<Product> adjustStock(String productId, int delta, String reason) =>
      _local.adjustStock(productId, delta, reason);
}
