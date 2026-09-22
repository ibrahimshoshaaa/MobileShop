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
  });
  Future<List<InstallmentPaymentRecord>> listPayments(String planId);
  Future<double> remaining(String planId);
  Future<InstallmentPaymentRecord> collectPayment({
    required String planId,
    required double amount,
    required PaymentMethod method,
  });
}
