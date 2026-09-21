import '../sales/sale_models.dart' show PaymentMethod, PaymentMethodX;
import '../maintenance/maintenance_models.dart';
import '../maintenance/maintenance_repository.dart';
import '../../core/api_client.dart';

class ApiMaintenanceRepository implements MaintenanceRepository {
  ApiMaintenanceRepository({required this.client});
  final ApiClient client;

  List<Map<String, dynamic>>? _wallets;

  Future<List<Map<String, dynamic>>> _getWallets() async {
    _wallets ??= await client.query('wallets');
    return _wallets!;
  }

  Future<String> _walletIdForMethod(PaymentMethod method) async {
    final wallets = await _getWallets();
    final wanted = method.wireValue;
    final w = wallets.firstWhere(
      (x) => (x['active'] as bool? ?? true) && x['wallet_type'] == wanted,
      orElse: () =>
          throw MaintenanceException('لا توجد محفظة مفعّلة لطريقة الدفع المحددة.'),
    );
    return w['id'] as String;
  }

  MaintenanceTicket _toTicket(
    Map<String, dynamic> d, {
    Map<String, String>? customerNames,
  }) {
    final customerId = d['customer_id'] as String;
    return MaintenanceTicket(
      id: d['id'] as String,
      customerId: customerId,
      customerName:
          customerNames?[customerId] ?? (d['customer_name'] as String? ?? customerId),
      device: d['device'] as String,
      imei: d['imei'] as String?,
      problem: d['problem'] as String,
      status: d['status'] as String? ?? 'RECEIVED',
      partsCost: double.parse((d['parts_cost'] ?? 0).toString()),
      finalCost: double.parse((d['final_cost'] ?? 0).toString()),
      payment: double.parse((d['payment'] ?? 0).toString()),
      createdAt: DateTime.parse(
        (d['created_at'] as String).replaceAll('Z', '+00:00'),
      ),
    );
  }

  MaintenancePartUsage _toPartUsage(Map<String, dynamic> d) =>
      MaintenancePartUsage(
        id: d['id'] as String,
        ticketId: d['ticket_id'] as String,
        productId: d['product_id'] as String,
        productName: d['product_name'] as String? ?? d['product_id'] as String,
        quantity: int.parse(d['quantity'].toString()),
        cost: double.parse(d['cost'].toString()),
        usedAt: DateTime.parse(
          (d['used_at'] as String).replaceAll('Z', '+00:00'),
        ),
      );

  @override
  Future<List<MaintenanceTicket>> listTickets() async {
    final raw = await client.query('maintenance');
    final customers = await client.query('customers');
    final customerNames = {
      for (final c in customers) c['id'] as String: c['name'] as String
    };
    return raw
        .map((d) => _toTicket(d, customerNames: customerNames))
        .toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  }

  @override
  Future<MaintenanceTicket> createTicket({
    required String customerId,
    required String customerName,
    required String device,
    String? imei,
    required String problem,
  }) async {
    if (device.trim().isEmpty || problem.trim().isEmpty) {
      throw MaintenanceException('الجهاز ووصف المشكلة مطلوبان.');
    }
    final data = await client.command(
      ApiClient.newCommandId('cmd-mnt'),
      'createMaintenanceTicket',
      {
        'customer_id': customerId,
        'device': device.trim(),
        'problem': problem.trim(),
        'imei': (imei?.trim().isEmpty ?? true) ? null : imei!.trim(),
      },
    );
    return _toTicket(data);
  }

  @override
  Future<MaintenanceTicket> advanceStatus(String ticketId) async {
    final tickets = await listTickets();
    final ticket =
        tickets.firstWhere((t) => t.id == ticketId,
            orElse: () => throw MaintenanceException('التذكرة غير موجودة.'));
    if (ticket.nextStatus == null) {
      throw MaintenanceException(
          'لا يمكن نقل الحالة الحالية (${ticket.statusLabel}) لمرحلة تالية.');
    }
    final data = await client.command(
      ApiClient.newCommandId('cmd-mnt-status'),
      'transitionMaintenance',
      {
        'ticket_id': ticketId,
        'new_status': ticket.nextStatus,
      },
    );
    return _toTicket(data);
  }

  @override
  Future<MaintenanceTicket> cancelTicket(String ticketId) async {
    final data = await client.command(
      ApiClient.newCommandId('cmd-mnt-cancel'),
      'cancelMaintenance',
      {'ticket_id': ticketId},
    );
    return _toTicket(data);
  }

  @override
  Future<List<MaintenancePartUsage>> listPartsUsed(String ticketId) async {
    final raw = await client.query('maintenance-parts');
    return raw
        .where((d) => d['ticket_id'] == ticketId)
        .map(_toPartUsage)
        .toList();
  }

  @override
  Future<MaintenancePartUsage> usePart({
    required String ticketId,
    required String productId,
    required String productName,
    required int quantity,
    required double cost,
  }) async {
    if (quantity <= 0) throw MaintenanceException('الكمية يجب أن تكون أكبر من صفر.');
    final data = await client.command(
      ApiClient.newCommandId('cmd-mnt-part'),
      'useMaintenancePart',
      {
        'ticket_id': ticketId,
        'product_id': productId,
        'quantity': quantity,
        'cost': cost,
      },
    );
    return _toPartUsage(data);
  }

  @override
  Future<MaintenanceTicket> deliverTicket({
    required String ticketId,
    required double finalPrice,
    required double payment,
    required PaymentMethod method,
  }) async {
    String? walletId;
    if (payment > 0) {
      walletId = await _walletIdForMethod(method);
    }
    final data = await client.command(
      ApiClient.newCommandId('cmd-mnt-deliver'),
      'deliverMaintenanceTicket',
      {
        'ticket_id': ticketId,
        'final_price': finalPrice,
        'payment': payment,
        'wallet_id': walletId,
      },
    );
    return _toTicket(data);
  }
}
