import '../sales/sale_models.dart' show PaymentMethod;
import 'installment_models.dart';

abstract class InstallmentRepository {
  Future<List<InstallmentPlan>> listPlans();
  Future<InstallmentPlan> createPlan({
    String? saleId,
    required String customerId,
    required String customerName,
    required double price,
    required double downPayment,
    required double ratePercent,
    required int termMonths,
    // Required whenever downPayment > 0 — the down payment is money taken
    // right now, so it needs a wallet to post into (locally and, when
    // pushable, on the server's down_payment_wallet_id). Left null when
    // downPayment == 0, where there's nothing to post.
    PaymentMethod? downPaymentMethod,
  });
  Future<List<InstallmentPaymentRecord>> listPayments(String planId);
  Future<double> remaining(String planId);
  Future<InstallmentPaymentRecord> collectPayment({
    required String planId,
    required double amount,
    required PaymentMethod method,
  });
}
