import 'dart:math';
import '../inventory/inventory_repository.dart';
import '../inventory/local_store.dart';
import '../sales/sale_models.dart' show PaymentMethod, PaymentMethodX;
import '../sync/online_push.dart';
import '../wallets/wallet_models.dart';
import '../wallets/wallet_provider.dart';
import 'maintenance_models.dart';
import 'maintenance_repository.dart';

class SqliteMaintenanceRepository implements MaintenanceRepository {
  SqliteMaintenanceRepository._(this._store, this._inventory);
  final LocalStore _store;
  final InventoryRepository _inventory;
  static const _ticketEntity = 'maintenance_ticket';
  static const _partEntity = 'maintenance_part';

  static Future<SqliteMaintenanceRepository> create(InventoryRepository inventory) async {
    final store = await LocalStore.open();
    return SqliteMaintenanceRepository._(store, inventory);
  }

  MaintenanceTicket _toTicket(Map<String, dynamic> p) => MaintenanceTicket(
        id: p['id'] as String,
        customerId: p['customer_id'] as String,
        customerName: p['customer_name'] as String,
        device: p['device'] as String,
        imei: p['imei'] as String?,
        problem: p['problem'] as String,
        status: p['status'] as String,
        partsCost: (p['parts_cost'] as num).toDouble(),
        finalCost: (p['final_cost'] as num).toDouble(),
        payment: (p['payment'] as num).toDouble(),
        createdAt: DateTime.parse(p['created_at'] as String),
      );

  Map<String, dynamic> _ticketPayload(MaintenanceTicket t) => {
        'id': t.id,
        'customer_id': t.customerId,
        'customer_name': t.customerName,
        'device': t.device,
        'imei': t.imei,
        'problem': t.problem,
        'status': t.status,
        'parts_cost': t.partsCost,
        'final_cost': t.finalCost,
        'payment': t.payment,
        'created_at': t.createdAt.toIso8601String(),
      };

  MaintenancePartUsage _toPart(Map<String, dynamic> p) => MaintenancePartUsage(
        id: p['id'] as String,
        ticketId: p['ticket_id'] as String,
        productId: p['product_id'] as String,
        productName: p['product_name'] as String,
        quantity: p['quantity'] as int,
        cost: (p['cost'] as num).toDouble(),
        usedAt: DateTime.parse(p['used_at'] as String),
      );

  Map<String, dynamic> _partPayload(MaintenancePartUsage p) => {
        'id': p.id,
        'ticket_id': p.ticketId,
        'product_id': p.productId,
        'product_name': p.productName,
        'quantity': p.quantity,
        'cost': p.cost,
        'used_at': p.usedAt.toIso8601String(),
      };

  String _newId(String prefix) => '$prefix-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(999999)}';

  @override
  Future<List<MaintenanceTicket>> listTickets() async {
    final rows = await _store.listRecords(entity: _ticketEntity);
    final tickets = rows.map((r) => _toTicket(r.payload)).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return tickets;
  }

  @override
  Future<MaintenanceTicket> createTicket({
    required String customerId,
    required String customerName,
    required String device,
    String? imei,
    required String problem,
  }) async {
    if (device.trim().isEmpty) throw MaintenanceException('يجب إدخال الجهاز.');
    if (problem.trim().isEmpty) throw MaintenanceException('يجب وصف المشكلة.');
    final ticket = MaintenanceTicket(
      id: _newId('mnt'),
      customerId: customerId,
      customerName: customerName,
      device: device.trim(),
      imei: (imei == null || imei.trim().isEmpty) ? null : imei.trim(),
      problem: problem.trim(),
      createdAt: DateTime.now(),
    );
    await _store.upsertRecord(entity: _ticketEntity, recordId: ticket.id, payload: _ticketPayload(ticket), expectedVersion: 0);
    // Reuses ticket.id as the command id, same reasoning as createSale in
    // sqlite_sale_repository.dart — so a successful online push leaves the
    // server's MaintenanceTicket under this same id, which usePart/
    // deliverTicket below rely on when they later reference [ticketId].
    await _store.queueCommand(
      commandId: ticket.id,
      command: 'createMaintenanceTicket',
      payload: {'customer_id': customerId, 'device': ticket.device, 'problem': ticket.problem, 'imei': ticket.imei},
    );
    await pushCommandOnline(_store, ticket.id, 'createMaintenanceTicket', {
      'customer_id': customerId,
      'device': ticket.device,
      'problem': ticket.problem,
      'imei': ticket.imei,
    });
    return ticket;
  }

  Future<({MaintenanceTicket ticket, int version})> _getTicket(String ticketId) async {
    final row = await _store.getRecord(entity: _ticketEntity, recordId: ticketId);
    if (row == null) throw MaintenanceException('طلب الصيانة غير موجود.');
    return (ticket: _toTicket(row.payload), version: row.version);
  }

  @override
  Future<MaintenanceTicket> advanceStatus(String ticketId) async {
    final current = await _getTicket(ticketId);
    final next = current.ticket.nextStatus;
    if (next == null) {
      throw MaintenanceException('لا يمكن نقل الحالة الحالية "${current.ticket.statusLabel}" لمرحلة تالية.');
    }
    final updated = current.ticket.copyWith(status: next);
    await _store.upsertRecord(
      entity: _ticketEntity, recordId: ticketId, payload: _ticketPayload(updated), expectedVersion: current.version,
    );
    final cmdId = _newId('cmd-mnt-status');
    final payload = {'ticket_id': ticketId, 'new_status': next};
    await _store.queueCommand(commandId: cmdId, command: 'transitionMaintenance', payload: payload);
    await pushCommandOnline(_store, cmdId, 'transitionMaintenance', payload);
    return updated;
  }

  @override
  Future<MaintenanceTicket> cancelTicket(String ticketId) async {
    final current = await _getTicket(ticketId);
    if (!current.ticket.isOpen) throw MaintenanceException('طلب الصيانة مغلق بالفعل.');
    final updated = current.ticket.copyWith(status: 'CANCELLED');
    await _store.upsertRecord(
      entity: _ticketEntity, recordId: ticketId, payload: _ticketPayload(updated), expectedVersion: current.version,
    );
    final cmdId = _newId('cmd-mnt-cancel');
    final payload = {'ticket_id': ticketId};
    await _store.queueCommand(commandId: cmdId, command: 'cancelMaintenance', payload: payload);
    await pushCommandOnline(_store, cmdId, 'cancelMaintenance', payload);
    return updated;
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
    final current = await _getTicket(ticketId);
    if (!current.ticket.isOpen) throw MaintenanceException('لا يمكن إضافة قطع لطلب مغلق.');

    // Decrement stock the same way Sales does — insufficient-stock check
    // happens inside adjustStock itself.
    // Local stock only: the server's useMaintenancePart already deducts stock itself.
    await _inventory.adjustStock(productId, -quantity, 'استخدام في صيانة #$ticketId', queueSync: false);

    final usage = MaintenancePartUsage(
      id: _newId('mntpart'), ticketId: ticketId, productId: productId, productName: productName,
      quantity: quantity, cost: cost, usedAt: DateTime.now(),
    );
    await _store.upsertRecord(entity: _partEntity, recordId: usage.id, payload: _partPayload(usage), expectedVersion: 0);

    final updatedTicket = current.ticket.copyWith(partsCost: current.ticket.partsCost + usage.total);
    await _store.upsertRecord(
      entity: _ticketEntity, recordId: ticketId, payload: _ticketPayload(updatedTicket),
      expectedVersion: current.version,
    );
    await _store.queueCommand(
      commandId: usage.id,
      command: 'useMaintenancePart',
      payload: {'ticket_id': ticketId, 'product_id': productId, 'quantity': quantity, 'cost': cost},
    );
    // `cost` is accepted but ignored server-side — use_maintenance_part in
    // erp_engine.py always recomputes it from the branch's own average
    // cost ("Inventory valuation is server-authoritative") — sent anyway
    // since it's a required positional in the function signature.
    await pushCommandOnline(_store, usage.id, 'useMaintenancePart', {
      'ticket_id': ticketId,
      'product_id': productId,
      'quantity': quantity,
      'cost': cost,
    });
    return usage;
  }

  @override
  Future<List<MaintenancePartUsage>> listPartsUsed(String ticketId) async {
    final rows = await _store.listRecords(entity: _partEntity);
    final parts = rows.map((r) => _toPart(r.payload)).where((p) => p.ticketId == ticketId).toList()
      ..sort((a, b) => a.usedAt.compareTo(b.usedAt));
    return parts;
  }

  @override
  Future<MaintenanceTicket> deliverTicket({
    required String ticketId,
    required double finalPrice,
    required double payment,
    required PaymentMethod method,
  }) async {
    final current = await _getTicket(ticketId);
    if (current.ticket.status != 'READY') {
      throw MaintenanceException('لا يمكن التسليم قبل أن تكون الحالة "جاهز للتسليم".');
    }
    if (finalPrice < 0 || payment < 0 || payment > finalPrice) {
      throw MaintenanceException('قيمة الدفع غير صحيحة.');
    }
    final updated = current.ticket.copyWith(status: 'DELIVERED', finalCost: finalPrice, payment: payment);
    await _store.upsertRecord(
      entity: _ticketEntity, recordId: ticketId, payload: _ticketPayload(updated), expectedVersion: current.version,
    );
    final deliverCmdId = _newId('cmd-mnt-deliver');
    final walletId = BuiltinWallets.tryFromWireValue(method.wireValue)?.id;
    final serverWalletId = serverWalletRefForMethod(method.wireValue);
    // Queue the wallet reference the server knows, not the payment-method name.
    await _store.queueCommand(
      commandId: deliverCmdId,
      command: 'deliverMaintenanceTicket',
      payload: {'ticket_id': ticketId, 'final_price': finalPrice, 'payment': payment, 'wallet_id': serverWalletId},
    );
    // Server only requires a wallet when payment > 0 (see
    // deliver_maintenance in completion.py); with no payment, wallet_id can
    // be omitted entirely, so a CREDIT delivery with payment 0 is still
    // safe to push. A CREDIT delivery *with* payment has no wallet to
    // attribute it to (same limitation as sales/expenses above), so that
    // combination is skipped — same as the local wallet posting just
    // below, gated on the same condition.
    if (payment == 0 || serverWalletId != null) {
      await pushCommandOnline(_store, deliverCmdId, 'deliverMaintenanceTicket', {
        'ticket_id': ticketId,
        'final_price': finalPrice,
        'payment': payment,
        'wallet_id': serverWalletId,
      });
    }
    if (walletId != null && payment > 0) {
      final wallets = await getWalletRepository();
      await wallets.postAuto(
        walletId: walletId,
        signedAmount: payment,
        type: WalletTxType.maintenance,
        note: 'تسليم صيانة #$ticketId',
      );
    }
    return updated;
  }
}
