import '../sales/sale_models.dart' show PaymentMethod;
import 'expense_models.dart';

abstract class ExpenseRepository {
  Future<List<Expense>> listExpenses({DateTime? from, DateTime? to});
  Future<Expense> addExpense({
    required double amount,
    required String category,
    required PaymentMethod method,
    String? note,
  });
  Future<double> totalForToday();
}
