import '../expenses/expense_provider.dart';
import '../inventory/inventory_provider.dart';
import '../maintenance/maintenance_provider.dart';
import '../sales/sales_provider.dart';
import 'reports_repository.dart';

Future<ReportsRepository>? _cachedRepositoryFuture;

/// The one place the app asks for "the" reports repository. Reuses the
/// already-cached sales/expense/maintenance/inventory repositories rather
/// than opening the store again.
Future<ReportsRepository> getReportsRepository() {
  return _cachedRepositoryFuture ??= _create();
}

Future<ReportsRepository> _create() async {
  final sales = await getSalesRepository();
  final expenses = await getExpenseRepository();
  final maintenance = await getMaintenanceRepository();
  final inventory = await getInventoryRepository();
  return ReportsRepository(
    salesRepository: sales,
    expenseRepository: expenses,
    maintenanceRepository: maintenance,
    inventoryRepository: inventory,
  );
}

void resetReportsRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
