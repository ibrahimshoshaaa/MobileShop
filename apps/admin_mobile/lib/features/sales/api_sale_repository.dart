import '../inventory/inventory_repository.dart';
import 'sale_models.dart';
import 'sale_repository.dart';
import '../../core/api_client.dart';

/// Online-mode sales repository.
/// Mirrors apps/desktop/api_sales_repo.py.
///
/// Key differences from offline mode:
/// - Payments map to wallet_id on the backend (wallets are pre-seeded per branch).
/// - CREDIT sales are sent without a payment entry — the backend creates a
///   customer ledger debit automatically.
/// - listRecentSales fetches wallets to resolve wallet_type → PaymentMethod.
class ApiSalesRepository implements SalesRepository {
  ApiSalesRepository({required this.client, required this.inventoryRepo});

  final ApiClient client;
  final InventoryRepository inventoryRepo;

  // Cached wallets for this session to avoid repeated round-trips.
  List<Map<String, dynamic>>? _wallets;

  Future<List<Map<String, dynamic>>> _getWallets() async {
    _wallets ??= await client.query('wallets');
    return _wallets!;
  }

  SaleRecord _toSaleRecord(
    Map<String, dynamic> d,
    Map<String, Map<String, dynamic>> walletsById,
  ) {
    final items = (d['items'] as List? ?? []).map((i) {
      final item = i as Map<String, dynamic>;
      return SaleItemRecord(
        productId: item['product_id'] as String,
        productName: (item['product_name'] as String?) ?? item['product_id'] as String,
        quantity: int.parse(item['quantity'].toString()),
        unitPrice: double.parse(item['unit_price'].toString()),
      );
    }).toList();

    final payments = (d['payments'] as List? ?? []).map((p) {
      final pay = p as Map<String, dynamic>;
      final walletId = pay['wallet_id'] as String? ?? '';
      final walletType = walletsById[walletId]?['wallet_type'] as String? ?? 'CASH';
      return PaymentEntry(
        method: PaymentMethodX.fromWireValue(walletType),
        amount: double.parse(pay['amount'].toString()),
      );
    }).toList();

    return SaleRecord(
      id: d['id'] as String,
      customerId: d['customer_id'] as String?,
      customerName: d['customer_name'] as String?,
      items: items,
      subtotal: double.parse(d['subtotal'].toString()),
      discount: double.parse((d['discount'] ?? 0).toString()),
      total: double.parse(d['total'].toString()),
      payments: payments,
      status: d['status'] as String? ?? 'COMPLETED',
      createdAt: DateTime.parse(
        (d['created_at'] as String).replaceAll('Z', '+00:00'),
      ),
    );
  }

  Future<String?> _walletIdForMethod(PaymentMethod method) async {
    if (method == PaymentMethod.credit) return null;
    final wallets = await _getWallets();
    final wanted = method.wireValue; // CASH / WALLET / CARD
    final wallet = wallets.firstWhere(
      (w) => (w['active'] as bool? ?? true) && w['wallet_type'] == wanted,
      orElse: () => throw SalesException(
        'لا توجد محفظة مفعّلة من نوع ${method.label} على السيرفر.',
      ),
    );
    return wallet['id'] as String;
  }

  @override
  Future<List<SaleRecord>> listRecentSales({int limit = 50}) async {
    final raw = await client.getSales(limit: limit);
    final wallets = await _getWallets();
    final walletsById = {for (final w in wallets) w['id'] as String: w};
    return raw.map((d) => _toSaleRecord(d, walletsById)).toList();
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

    final subtotal = items.fold<double>(0, (s, i) => s + i.lineTotal);
    final total = subtotal - discount;
    if (total < 0) throw SalesException('الخصم أكبر من إجمالي الفاتورة.');

    final paid = payments.fold<double>(0, (s, p) => s + p.amount);
    final isCredit = payments.any((p) => p.method == PaymentMethod.credit);
    if (!isCredit && (paid - total).abs() > 0.01) {
      throw SalesException(
        'إجمالي المدفوعات (${paid.toStringAsFixed(2)}) لا يساوي إجمالي الفاتورة (${total.toStringAsFixed(2)}).',
      );
    }

    // Map payments to wallet IDs (skip credit entries — backend handles them).
    final apiPayments = <Map<String, dynamic>>[];
    for (final p in payments) {
      if (p.method == PaymentMethod.credit) continue;
      final walletId = await _walletIdForMethod(p.method);
      if (walletId == null) continue;
      apiPayments.add({'wallet_id': walletId, 'amount': p.amount});
    }

    final data = await client.command(
      ApiClient.newCommandId('cmd-sale'),
      'createSale',
      {
        'customer_id': customerId,
        'items': items.map((i) => {
          'product_id': i.productId,
          'quantity': i.quantity,
          'unit_price': i.unitPrice,
        }).toList(),
        'payments': apiPayments,
        'discount': discount,
      },
    );

    final wallets = await _getWallets();
    final walletsById = {for (final w in wallets) w['id'] as String: w};
    return _toSaleRecord(data, walletsById);
  }

  @override
  Future<SaleRecord> voidSale(String saleId) async {
    final data = await client.command(
      ApiClient.newCommandId('cmd-void'),
      'voidSale',
      {'sale_id': saleId},
    );
    final wallets = await _getWallets();
    final walletsById = {for (final w in wallets) w['id'] as String: w};
    return _toSaleRecord(data, walletsById);
  }
}
