import 'dart:math';
import '../inventory/local_store.dart';
import '../sales/sale_models.dart' show PaymentMethod, PaymentMethodX;
import '../wallets/wallet_models.dart';
import '../wallets/wallet_provider.dart';
import 'expense_models.dart';
import 'expense_repository.dart';

class SqliteExpenseRepository implements ExpenseRepository {
  SqliteExpenseRepository._(this._store);
  final LocalStore _store;
  static const _entity = 'expense';

  static Future<SqliteExpenseRepository> create() async {
    final store = await LocalStore.open();
    return SqliteExpenseRepository._(store);
  }

  Expense _toExpense(Map<String, dynamic> payload) => Expense(
        id: payload['id'] as String,
        amount: (payload['amount'] as num).toDouble(),
        category: payload['category'] as String,
        method: PaymentMethodX.fromWireValue(payload['wallet_id'] as String),
        note: payload['note'] as String?,
        createdAt: DateTime.parse(payload['created_at'] as String),
      );

  Map<String, dynamic> _toPayload(Expense e) => {
        'id': e.id,
        'amount': e.amount,
        'category': e.category,
        'wallet_id': e.method.wireValue,
        'note': e.note,
        'created_at': e.createdAt.toIso8601String(),
      };

  @override
  Future<List<Expense>> listExpenses({DateTime? from, DateTime? to}) async {
    final rows = await _store.listRecords(entity: _entity);
    var expenses = rows.map((r) => _toExpense(r.payload)).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    if (from != null) expenses = expenses.where((e) => !e.createdAt.isBefore(from)).toList();
    if (to != null) expenses = expenses.where((e) => !e.createdAt.isAfter(to)).toList();
    return expenses;
  }

  @override
  Future<Expense> addExpense({
    required double amount,
    required String category,
    required PaymentMethod method,
    String? note,
  }) async {
    if (amount <= 0) throw ExpenseException('قيمة المصروف يجب أن تكون موجبة.');
    if (category.trim().isEmpty) throw ExpenseException('يجب اختيار تصنيف للمصروف.');
    final expense = Expense(
      id: _newId(),
      amount: amount,
      category: category,
      method: method,
      note: (note == null || note.trim().isEmpty) ? null : note.trim(),
      createdAt: DateTime.now(),
    );
    await _store.upsertRecord(entity: _entity, recordId: expense.id, payload: _toPayload(expense), expectedVersion: 0);
    await _store.queueCommand(
      commandId: _newId(prefix: 'cmd-expense'),
      command: 'createExpense',
      payload: {
        'wallet_id': method.wireValue,
        'amount': amount,
        'category': category,
        'note': expense.note,
      },
    );
    final walletId = WalletIdX.tryFromWireValue(method.wireValue);
    if (walletId != null) {
      final wallets = await getWalletRepository();
      await wallets.postAuto(
        walletId: walletId,
        signedAmount: -amount,
        type: WalletTxType.expense,
        note: category,
      );
    }
    return expense;
  }

  @override
  Future<double> totalForToday() async {
    final now = DateTime.now();
    final startOfDay = DateTime(now.year, now.month, now.day);
    final expenses = await listExpenses(from: startOfDay);
    return expenses.fold<double>(0, (sum, e) => sum + e.amount);
  }

  String _newId({String prefix = 'exp'}) => '$prefix-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(999999)}';
}
