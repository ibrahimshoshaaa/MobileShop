import 'dart:math';
import 'sale_models.dart';

/// Abstraction the UI depends on. The real app uses SqliteSalesRepository
/// (see sales_provider.dart); this interface is what both that and the
/// eventual backend command boundary (CreateSaleCommand in
/// shared/contracts/commands.py, executed via backend/functions/commands/sale.py)
/// need to satisfy.
abstract class SalesRepository {
  Future<List<SaleRecord>> listRecentSales({int limit = 50});
  Future<SaleRecord> createSale({
    required List<SaleItemRecord> items,
    required List<PaymentEntry> payments,
    String? customerId,
    String? customerName,
    double discount = 0,
  });
  Future<SaleRecord> voidSale(String saleId);
}

class InMemorySalesRepository implements SalesRepository {
  final List<SaleRecord> _sales = [];

  @override
  Future<List<SaleRecord>> listRecentSales({int limit = 50}) async {
    final sorted = [..._sales]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return sorted.take(limit).toList(growable: false);
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
    final subtotal = items.fold<double>(0, (sum, i) => sum + i.lineTotal);
    final total = subtotal - discount;
    final paid = payments.fold<double>(0, (sum, p) => sum + p.amount);
    if ((paid - total).abs() > 0.01) {
      throw SalesException('إجمالي المدفوعات لا يساوي إجمالي الفاتورة.');
    }
    final sale = SaleRecord(
      id: 'sale-${Random().nextInt(999999)}',
      customerId: customerId,
      customerName: customerName,
      items: items,
      subtotal: subtotal,
      discount: discount,
      total: total,
      payments: payments,
      status: 'COMPLETED',
      createdAt: DateTime.now(),
    );
    _sales.add(sale);
    return sale;
  }

  @override
  Future<SaleRecord> voidSale(String saleId) async {
    final idx = _sales.indexWhere((s) => s.id == saleId);
    if (idx == -1) throw SalesException('الفاتورة غير موجودة.');
    if (_sales[idx].status == 'VOIDED') throw SalesException('الفاتورة ملغاة بالفعل.');
    _sales[idx] = _sales[idx].copyWith(status: 'VOIDED');
    return _sales[idx];
  }
}
