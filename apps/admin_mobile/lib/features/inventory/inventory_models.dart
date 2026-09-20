import 'package:flutter/material.dart';

/// Mirrors shared/enums/domain.py ProductType — keep in sync with the backend enum.
enum ProductType { phoneNew, phoneUsed, accessory, sparePart, service }

extension ProductTypeX on ProductType {
  String get label => switch (this) {
        ProductType.phoneNew => 'الهواتف الجديدة',
        ProductType.phoneUsed => 'الهواتف المستعملة',
        ProductType.accessory => 'الإكسسوارات',
        ProductType.sparePart => 'قطع الغيار',
        ProductType.service => 'الخدمات',
      };

  IconData get icon => switch (this) {
        ProductType.phoneNew => Icons.smartphone,
        ProductType.phoneUsed => Icons.phone_android,
        ProductType.accessory => Icons.headphones,
        ProductType.sparePart => Icons.memory,
        ProductType.service => Icons.build,
      };

  /// Value sent to/received from the backend command layer (must match the Python StrEnum value).
  String get wireValue => switch (this) {
        ProductType.phoneNew => 'PHONE_NEW',
        ProductType.phoneUsed => 'PHONE_USED',
        ProductType.accessory => 'ACCESSORY',
        ProductType.sparePart => 'SPARE_PART',
        ProductType.service => 'SERVICE',
      };

  static ProductType fromWireValue(String value) => switch (value) {
        'PHONE_NEW' => ProductType.phoneNew,
        'PHONE_USED' => ProductType.phoneUsed,
        'ACCESSORY' => ProductType.accessory,
        'SPARE_PART' => ProductType.sparePart,
        'SERVICE' => ProductType.service,
        _ => throw ArgumentError('Unknown ProductType wire value: $value'),
      };
}

/// Mobile-side view of shared/models/erp.py Product, with an aggregated on-hand
/// quantity folded in for display. Serial/IMEI-tracked units (ProductUnit) are
/// out of scope here — see the maintenance/IMEI lifecycle work in the status doc.
@immutable
class Product {
  final String id;
  final String name;
  final String sku;
  final ProductType type;
  final String? barcode;
  final double sellingPrice;
  final double defaultCost;
  final int reorderLevel;
  final int quantity;
  final bool active;

  const Product({
    required this.id,
    required this.name,
    required this.sku,
    required this.type,
    this.barcode,
    required this.sellingPrice,
    required this.defaultCost,
    required this.reorderLevel,
    required this.quantity,
    this.active = true,
  });

  bool get isLowStock => quantity <= reorderLevel;

  Product copyWith({
    String? name,
    String? sku,
    ProductType? type,
    String? barcode,
    double? sellingPrice,
    double? defaultCost,
    int? reorderLevel,
    int? quantity,
    bool? active,
  }) {
    return Product(
      id: id,
      name: name ?? this.name,
      sku: sku ?? this.sku,
      type: type ?? this.type,
      barcode: barcode ?? this.barcode,
      sellingPrice: sellingPrice ?? this.sellingPrice,
      defaultCost: defaultCost ?? this.defaultCost,
      reorderLevel: reorderLevel ?? this.reorderLevel,
      quantity: quantity ?? this.quantity,
      active: active ?? this.active,
    );
  }
}

class InventoryException implements Exception {
  final String message;
  InventoryException(this.message);
  @override
  String toString() => message;
}
