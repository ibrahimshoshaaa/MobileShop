import 'package:flutter/foundation.dart';

/// Payment method for one payment line on a sale. "دفع مختلط" (mixed) isn't
/// its own value — it's just a sale with more than one payment line using
/// different methods, same as the placeholder screen described.
enum PaymentMethod { cash, wallet, card, credit }

extension PaymentMethodX on PaymentMethod {
  String get label => switch (this) {
        PaymentMethod.cash => 'نقدي',
        PaymentMethod.wallet => 'محفظة',
        PaymentMethod.card => 'بطاقة',
        PaymentMethod.credit => 'آجل',
      };

  /// Matches the wallet_type / Payment.wallet_id concept in shared/models/erp.py.
  String get wireValue => switch (this) {
        PaymentMethod.cash => 'CASH',
        PaymentMethod.wallet => 'WALLET',
        PaymentMethod.card => 'CARD',
        PaymentMethod.credit => 'CREDIT',
      };

  static PaymentMethod fromWireValue(String value) => switch (value) {
        'CASH' => PaymentMethod.cash,
        'WALLET' => PaymentMethod.wallet,
        'CARD' => PaymentMethod.card,
        'CREDIT' => PaymentMethod.credit,
        _ => throw ArgumentError('Unknown PaymentMethod wire value: $value'),
      };
}

@immutable
class PaymentEntry {
  final PaymentMethod method;
  final double amount;
  const PaymentEntry({required this.method, required this.amount});
}

/// A line in a sale, once committed. Snapshots the product name/price at
/// sale time (matches SaleItem.cost_snapshot in the Python model) so the
/// invoice reads correctly even if the product is edited/deleted later.
@immutable
class SaleItemRecord {
  final String productId;
  final String productName;
  final int quantity;
  final double unitPrice;
  const SaleItemRecord({
    required this.productId,
    required this.productName,
    required this.quantity,
    required this.unitPrice,
  });
  double get lineTotal => quantity * unitPrice;
}

@immutable
class SaleRecord {
  final String id;
  final String? customerId;
  final String? customerName;
  final List<SaleItemRecord> items;
  final double subtotal;
  final double discount;
  final double total;
  final List<PaymentEntry> payments;
  final String status; // 'COMPLETED' | 'VOIDED'
  final DateTime createdAt;

  const SaleRecord({
    required this.id,
    required this.customerId,
    this.customerName,
    required this.items,
    required this.subtotal,
    required this.discount,
    required this.total,
    required this.payments,
    required this.status,
    required this.createdAt,
  });

  SaleRecord copyWith({String? status}) => SaleRecord(
        id: id,
        customerId: customerId,
        customerName: customerName,
        items: items,
        subtotal: subtotal,
        discount: discount,
        total: total,
        payments: payments,
        status: status ?? this.status,
        createdAt: createdAt,
      );
}

class SalesException implements Exception {
  final String message;
  SalesException(this.message);
  @override
  String toString() => message;
}
