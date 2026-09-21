import '../sales/sale_models.dart' show PaymentMethod, PaymentMethodX;
import '../expenses/expense_models.dart';
import '../expenses/expense_repository.dart';
import '../../core/api_client.dart';

class ApiExpenseRepository implements ExpenseRepository {
  ApiExpenseRepository({required this.client});
  final ApiClient client;

  List<Map<String, dynamic>>? _wallets;

  Future<List<Map<String, dynamic>>> _getWallets() async {
    _wallets ??= await client.query('wallets');
    return _wallets!;
  }

  Future<String> _walletIdForMethod(PaymentMethod method) async {
    final wallets = await _getWallets();
    final wanted = method.wireValue; // CASH / WALLET / CARD
    final w = wallets.firstWhere(
      (x) => (x['active'] as bool? ?? true) && x['wallet_type'] == wanted,
      orElse: () => throw ExpenseException(
          'لا توجد محفظة مفعّلة من نوع ${method.label} على السيرفر.'),
    );
    return w['id'] as String;
  }

  Expense _toExpense(Map<String, dynamic> d, Map<String, Map<String, dynamic>> walletsById) {
    final walletId = d['wallet_id'] as String? ?? '';
    final walletType = walletsById[walletId]?['wallet_type'] as String? ?? 'CASH';
    return Expense(
      id: d['id'] as String,
      amount: double.parse(d['amount'].toString()),
      category: d['category'] as String,
      method: PaymentMethodX.fromWireValue(walletType),
      note: d['note'] as String?,
      createdAt: DateTime.parse(
        (d['created_at'] as String).replaceAll('Z', '+00:00'),
      ),
    );
  }

  @override
  Future<List<Expense>> listExpenses({DateTime? from, DateTime? to}) async {
    final raw = await client.query('expenses');
    final wallets = await _getWallets();
    final walletsById = {for (final w in wallets) w['id'] as String: w};
    final all = raw.map((d) => _toExpense(d, walletsById)).toList();
    return all.where((e) {
      if (from != null && e.createdAt.isBefore(from)) return false;
      if (to != null && e.createdAt.isAfter(to)) return false;
      return true;
    }).toList();
  }

  @override
  Future<double> totalForToday() async {
    final today = DateTime.now();
    final todayDate = DateTime(today.year, today.month, today.day);
    final expenses = await listExpenses(from: todayDate);
    return expenses.fold<double>(0, (s, e) => s + e.amount);
  }

  @override
  Future<Expense> addExpense({
    required double amount,
    required String category,
    required PaymentMethod method,
    String? note,
  }) async {
    if (amount <= 0) throw ExpenseException('قيمة المصروف يجب أن تكون موجبة.');
    final walletId = await _walletIdForMethod(method);
    final data = await client.command(
      ApiClient.newCommandId('cmd-expense'),
      'createExpense',
      {
        'wallet_id': walletId,
        'amount': amount,
        'category': category,
        'note': note,
      },
    );
    final wallets = await _getWallets();
    final walletsById = {for (final w in wallets) w['id'] as String: w};
    return _toExpense(data, walletsById);
  }
}
