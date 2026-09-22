import 'package:flutter/foundation.dart';

/// Mirrors ERPCommandEngine._MAINT in backend/functions/services/erp_engine.py
/// exactly — each status can only advance to the one named here (no skipping
/// steps), plus a separate 'CANCELLED' terminal state reachable from any
/// status via cancelTicket.
const Map<String, String> maintenanceNextStatus = {
  'RECEIVED': 'DIAGNOSING',
  'DIAGNOSING': 'WAITING_CUSTOMER',
  'WAITING_CUSTOMER': 'IN_PROGRESS',
  'IN_PROGRESS': 'READY',
  'READY': 'DELIVERED',
};

const Map<String, String> maintenanceStatusLabels = {
  'RECEIVED': 'تم الاستلام',
  'DIAGNOSING': 'جارِ الفحص',
  'WAITING_CUSTOMER': 'بانتظار العميل',
  'IN_PROGRESS': 'جارِ الإصلاح',
  'READY': 'جاهز للتسليم',
  'DELIVERED': 'تم التسليم',
  'CANCELLED': 'ملغي',
};

@immutable
class MaintenanceTicket {
  final String id;
  final String customerId;
  final String customerName;
  final String device;
  final String? imei;
  final String problem;
  final String status;
  final double partsCost;
  final double finalCost;
  final double payment;
  final DateTime createdAt;

  const MaintenanceTicket({
    required this.id,
    required this.customerId,
    required this.customerName,
    required this.device,
    this.imei,
    required this.problem,
    this.status = 'RECEIVED',
    this.partsCost = 0,
    this.finalCost = 0,
    this.payment = 0,
    required this.createdAt,
  });

  String get statusLabel => maintenanceStatusLabels[status] ?? status;
  bool get isOpen => status != 'DELIVERED' && status != 'CANCELLED';
  String? get nextStatus => maintenanceNextStatus[status];

  MaintenanceTicket copyWith({String? status, double? partsCost, double? finalCost, double? payment}) =>
      MaintenanceTicket(
        id: id,
        customerId: customerId,
        customerName: customerName,
        device: device,
        imei: imei,
        problem: problem,
        status: status ?? this.status,
        partsCost: partsCost ?? this.partsCost,
        finalCost: finalCost ?? this.finalCost,
        payment: payment ?? this.payment,
        createdAt: createdAt,
      );
}

@immutable
class MaintenancePartUsage {
  final String id;
  final String ticketId;
  final String productId;
  final String productName;
  final int quantity;
  final double cost;
  final DateTime usedAt;

  const MaintenancePartUsage({
    required this.id,
    required this.ticketId,
    required this.productId,
    required this.productName,
    required this.quantity,
    required this.cost,
    required this.usedAt,
  });

  double get total => quantity * cost;
}

class MaintenanceException implements Exception {
  final String message;
  MaintenanceException(this.message);
  @override
  String toString() => message;
}
