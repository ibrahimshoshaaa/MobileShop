import '../sales/sale_models.dart' show PaymentMethod, PaymentMethodX;
import '../installments/installment_models.dart';
import '../installments/installment_repository.dart';
import '../../core/api_client.dart';

class ApiInstallmentRepository implements InstallmentRepository {
  ApiInstallmentRepository({required this.client});
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
      orElse: () => throw InstallmentException(
          'لا توجد محفظة مفعّلة لطريقة الدفع المحددة.'),
    );
    return w['id'] as String;
  }

  InstallmentPlan _toPlan(
    Map<String, dynamic> d, {
    Map<String, String>? customerNames,
  }) {
    final customerId = d['customer_id'] as String;
    return InstallmentPlan(
      id: d['id'] as String,
      saleId: d['sale_id'] as String?,
      customerId: customerId,
      customerName:
          customerNames?[customerId] ?? (d['customer_name'] as String? ?? customerId),
      baseFinanced: double.parse(d['base_financed'].toString()),
      ratePercent: double.parse(d['rate_percent'].toString()),
      increase: double.parse(d['increase'].toString()),
      totalDue: double.parse(d['total_due'].toString()),
      termMonths: int.parse(d['term_months'].toString()),
      monthlyAmount: double.parse(d['monthly_amount'].toString()),
      createdAt: DateTime.parse(
        (d['created_at'] as String).replaceAll('Z', '+00:00'),
      ),
    );
  }

  InstallmentPaymentRecord _toPaymentRecord(
    Map<String, dynamic> d,
    Map<String, Map<String, dynamic>> walletsById,
  ) {
    final walletId = d['wallet_id'] as String? ?? '';
    final walletType =
        walletsById[walletId]?['wallet_type'] as String? ?? 'CASH';
    return InstallmentPaymentRecord(
      id: d['id'] as String,
      planId: d['plan_id'] as String,
      amount: double.parse(d['amount'].toString()),
      method: PaymentMethodX.fromWireValue(walletType),
      paidAt: DateTime.parse(
        (d['paid_at'] as String).replaceAll('Z', '+00:00'),
      ),
    );
  }

  @override
  Future<List<InstallmentPlan>> listPlans() async {
    final rawPlans = await client.query('installments');
    final customers = await client.query('customers');
    final customerNames = {
      for (final c in customers) c['id'] as String: c['name'] as String
    };
    return rawPlans
        .map((d) => _toPlan(d, customerNames: customerNames))
        .toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  }

  @override
  Future<InstallmentPlan> createPlan({
    String? saleId,
    required String customerId,
    required String customerName,
    required double price,
    required double downPayment,
    required double ratePercent,
    required int termMonths,
  }) async {
    // Online mode requires a linked sale (backend enforces it).
    if (saleId == null) {
      throw InstallmentException(
          'إنشاء التقسيط Online يحتاج رقم فاتورة مرتبطة.');
    }
    String? walletId;
    if (downPayment > 0) {
      walletId = await _walletIdForMethod(PaymentMethod.cash);
    }
    final data = await client.command(
      ApiClient.newCommandId('cmd-plan'),
      'createInstallmentPlan',
      {
        'sale_id': saleId,
        'customer_id': customerId,
        'down_payment': downPayment,
        'rate_percent': ratePercent,
        'term_months': termMonths,
        'down_payment_wallet_id': walletId,
      },
    );
    return _toPlan(data);
  }

  @override
  Future<List<InstallmentPaymentRecord>> listPayments(String planId) async {
    final rawPayments = await client.query('installment-payments');
    final wallets = await _getWallets();
    final walletsById = {for (final w in wallets) w['id'] as String: w};
    return rawPayments
        .where((d) => d['plan_id'] == planId)
        .map((d) => _toPaymentRecord(d, walletsById))
        .toList();
  }

  @override
  Future<double> remaining(String planId) async {
    final plans = await listPlans();
    final plan = plans.firstWhere(
      (p) => p.id == planId,
      orElse: () => throw InstallmentException('خطة التقسيط غير موجودة.'),
    );
    final payments = await listPayments(planId);
    final paid = payments.fold<double>(0, (s, p) => s + p.amount);
    return (plan.totalDue - paid).clamp(0, double.infinity);
  }

  @override
  Future<InstallmentPaymentRecord> collectPayment({
    required String planId,
    required double amount,
    required PaymentMethod method,
  }) async {
    if (amount <= 0) throw InstallmentException('المبلغ يجب أن يكون أكبر من صفر.');
    final walletId = await _walletIdForMethod(method);
    final data = await client.command(
      ApiClient.newCommandId('cmd-collect'),
      'collectInstallment',
      {
        'installment_id': planId,
        'amount': amount,
        'wallet_id': walletId,
      },
    );
    final wallets = await _getWallets();
    final walletsById = {for (final w in wallets) w['id'] as String: w};
    return _toPaymentRecord(data, walletsById);
  }
}
