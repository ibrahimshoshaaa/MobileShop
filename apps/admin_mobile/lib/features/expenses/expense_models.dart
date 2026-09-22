import 'package:flutter/foundation.dart';
import '../sales/sale_models.dart' show PaymentMethod;

/// Deviation from shared/models/erp.py Expense: the backend deducts from a
/// real wallet balance (checked against the ledger) and only allows the
/// expense if that wallet can cover it. This mobile app has no wallet/ledger
/// concept at all yet (sales just record which PaymentMethod was used, not
/// a running balance) — so an expense here records which method it came out
/// of without checking any balance. A real balance check needs the wallet
/// system to exist first; this is the same "no ledger yet" simplification
/// already made throughout inventory/sales/installments.
const List<String> expenseCategories = [
  'إيجار', 'كهرباء ومياه', 'رواتب', 'صيانة', 'نقل وتوصيل', 'أخرى',
];

@immutable
class Expense {
  final String id;
  final double amount;
  final String category;
  final PaymentMethod method;
  final String? note;
  final DateTime createdAt;

  const Expense({
    required this.id,
    required this.amount,
    required this.category,
    required this.method,
    this.note,
    required this.createdAt,
  });
}

class ExpenseException implements Exception {
  final String message;
  ExpenseException(this.message);
  @override
  String toString() => message;
}
