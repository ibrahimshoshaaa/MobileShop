import 'package:flutter/foundation.dart';
import '../sales/sale_models.dart' show PaymentMethod;

/// Deviation from shared/models/erp.py InstallmentPlan (there sale_id is
/// required): this mobile flow lets a plan be created directly against a
/// customer, not only from a completed Sale record, to support layaway-style
/// financing that isn't tied to a single cash-register invoice. [saleId] is
/// kept nullable to allow linking one in later if that flow gets built.
@immutable
class InstallmentPlan {
  final String id;
  final String? saleId;
  final String customerId;
  final String customerName;
  final double baseFinanced;
  final double ratePercent;
  final double increase;
  final double totalDue;
  final int termMonths;
  final double monthlyAmount;
  final DateTime createdAt;

  const InstallmentPlan({
    required this.id,
    this.saleId,
    required this.customerId,
    required this.customerName,
    required this.baseFinanced,
    required this.ratePercent,
    required this.increase,
    required this.totalDue,
    required this.termMonths,
    required this.monthlyAmount,
    required this.createdAt,
  });
}

@immutable
class InstallmentPaymentRecord {
  final String id;
  final String planId;
  final double amount;
  final PaymentMethod method;
  final DateTime paidAt;

  const InstallmentPaymentRecord({
    required this.id,
    required this.planId,
    required this.amount,
    required this.method,
    required this.paidAt,
  });
}

@immutable
class InstallmentCalculation {
  final double baseFinanced;
  final double increase;
  final double totalDue;
  final double monthlyAmount;
  const InstallmentCalculation({
    required this.baseFinanced,
    required this.increase,
    required this.totalDue,
    required this.monthlyAmount,
  });
}

class InstallmentException implements Exception {
  final String message;
  InstallmentException(this.message);
  @override
  String toString() => message;
}

/// Mirrors InstallmentService.calculate: base = price - down_payment,
/// increase = base * rate% (rounded), total = base + increase,
/// monthly = total / term_months (rounded).
///
/// Note: this rounds doubles, not Decimals like the Python side — for typical
/// shop prices (2 decimal places, no huge sums) the result matches, but this
/// is not the exact-decimal guarantee the backend gives; a server-side
/// recompute should be the final word once the API exists.
InstallmentCalculation calculateInstallment({
  required double price,
  required double downPayment,
  required double ratePercent,
  required int termMonths,
}) {
  if (termMonths <= 0) throw InstallmentException('عدد الأشهر يجب أن يكون أكبر من صفر.');
  if (downPayment < 0) throw InstallmentException('المقدم لا يمكن أن يكون سالبًا.');
  if (downPayment > price) throw InstallmentException('المقدم أكبر من السعر الإجمالي.');

  final base = price - downPayment;
  final increase = _roundTo2(base * ratePercent / 100);
  final total = base + increase;
  final monthly = _roundTo2(total / termMonths);
  return InstallmentCalculation(baseFinanced: base, increase: increase, totalDue: total, monthlyAmount: monthly);
}

double _roundTo2(double value) => (value * 100).round() / 100;
