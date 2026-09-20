import 'dart:math';
import 'inventory_models.dart';

/// Abstraction the UI depends on. [InMemoryInventoryRepository] below is a
/// simple in-memory implementation kept around for tests/dev; the app itself
/// uses SqliteInventoryRepository (see inventory_provider.dart) so data
/// survives restarts, and calls the backend command/query boundary
/// (createProduct / adjustStock commands in backend/functions/commands/stock.py)
/// once the API is deployed — the UI does not need to change.
abstract class InventoryRepository {
  Future<List<Product>> listProducts({ProductType? type, String query = ''});
  Future<Product> addProduct({
    required String name,
    required String sku,
    required ProductType type,
    String? barcode,
    required double sellingPrice,
    required double defaultCost,
    required int reorderLevel,
    required int openingQuantity,
  });
  Future<Product> updateProduct(Product product);
  Future<Product> adjustStock(String productId, int delta, String reason);
}

class InMemoryInventoryRepository implements InventoryRepository {
  InMemoryInventoryRepository() {
    _products.addAll(_seed());
  }

  final List<Product> _products = [];
  final _latency = const Duration(milliseconds: 220);

  List<Product> _seed() => [
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
          barcode: null,
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
          barcode: null,
          sellingPrice: 150,
          defaultCost: 0,
          reorderLevel: 0,
          quantity: 0,
        ),
      ];

  @override
  Future<List<Product>> listProducts({ProductType? type, String query = ''}) async {
    await Future.delayed(_latency);
    final q = query.trim().toLowerCase();
    return _products.where((p) {
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
    await Future.delayed(_latency);
    if (_products.any((p) => p.sku.toLowerCase() == sku.toLowerCase())) {
      throw InventoryException('رمز الصنف (SKU) "$sku" مستخدم بالفعل.');
    }
    if (barcode != null && barcode.isNotEmpty && _products.any((p) => p.barcode == barcode)) {
      throw InventoryException('الباركود مستخدم بالفعل لصنف آخر.');
    }
    final product = Product(
      id: 'p${Random().nextInt(999999)}',
      name: name,
      sku: sku,
      type: type,
      barcode: (barcode == null || barcode.isEmpty) ? null : barcode,
      sellingPrice: sellingPrice,
      defaultCost: defaultCost,
      reorderLevel: reorderLevel,
      quantity: openingQuantity,
    );
    _products.add(product);
    return product;
  }

  @override
  Future<Product> updateProduct(Product product) async {
    await Future.delayed(_latency);
    final idx = _products.indexWhere((p) => p.id == product.id);
    if (idx == -1) throw InventoryException('الصنف غير موجود.');
    final skuClash = _products.any((p) => p.id != product.id && p.sku.toLowerCase() == product.sku.toLowerCase());
    if (skuClash) throw InventoryException('رمز الصنف (SKU) مستخدم بالفعل لصنف آخر.');
    _products[idx] = product;
    return product;
  }

  @override
  Future<Product> adjustStock(String productId, int delta, String reason) async {
    await Future.delayed(_latency);
    final idx = _products.indexWhere((p) => p.id == productId);
    if (idx == -1) throw InventoryException('الصنف غير موجود.');
    if (reason.trim().isEmpty) throw InventoryException('يجب إدخال سبب حركة المخزون.');
    final newQty = _products[idx].quantity + delta;
    if (newQty < 0) {
      throw InventoryException('الكمية الناتجة سالبة — تحقق من الرصيد الحالي.');
    }
    _products[idx] = _products[idx].copyWith(quantity: newQty);
    return _products[idx];
  }
}
