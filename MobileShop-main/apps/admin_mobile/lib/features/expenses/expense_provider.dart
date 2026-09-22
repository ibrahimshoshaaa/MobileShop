import 'expense_repository.dart';
import 'sqlite_expense_repository.dart';

Future<ExpenseRepository>? _cachedRepositoryFuture;

Future<ExpenseRepository> getExpenseRepository() {
  return _cachedRepositoryFuture ??= SqliteExpenseRepository.create();
}

void resetExpenseRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
