import '../features/inventory/inventory_repository.dart';
import '../features/inventory/sqlite_inventory_repository.dart';
import '../features/inventory/api_inventory_repository.dart';
import '../features/sales/sale_repository.dart';
import '../features/sales/sqlite_sale_repository.dart';
import '../features/sales/api_sale_repository.dart';
import '../features/customers/customer_repository.dart';
import '../features/customers/sqlite_customer_repository.dart';
import '../features/customers/api_customer_repository.dart';
import '../features/suppliers/supplier_repository.dart';
import '../features/suppliers/sqlite_supplier_repository.dart';
import '../features/suppliers/api_supplier_repository.dart';
import '../features/expenses/expense_repository.dart';
import '../features/expenses/sqlite_expense_repository.dart';
import '../features/expenses/api_expense_repository.dart';
import '../features/installments/installment_repository.dart';
import '../features/installments/sqlite_installment_repository.dart';
import '../features/installments/api_installment_repository.dart';
import '../features/maintenance/maintenance_repository.dart';
import '../features/maintenance/sqlite_maintenance_repository.dart';
import '../features/maintenance/api_maintenance_repository.dart';
import 'app_config.dart';
import 'api_client.dart';

/// Single factory — returns offline (SQLite) or online (API) repo based on AppConfig.
/// All repos are cached; call [resetAllRepositories] + restart when mode changes.

ApiClient? _apiClient;
InventoryRepository? _inventory;
SalesRepository? _sales;
CustomerRepository? _customers;
SupplierRepository? _suppliers;
ExpenseRepository? _expenses;
InstallmentRepository? _installments;
MaintenanceRepository? _maintenance;

Future<ApiClient> _getClient() async {
  if (_apiClient != null) return _apiClient!;
  final cfg = await AppConfig.load();
  _apiClient = ApiClient(
    baseUrl: cfg.apiUrl,
    token: cfg.apiToken,
    branchId: 'LOCAL_BRANCH',
  );
  return _apiClient!;
}

Future<InventoryRepository> getInventoryRepository() async {
  if (_inventory != null) return _inventory!;
  final cfg = await AppConfig.load();
  _inventory = cfg.onlineMode
      ? ApiInventoryRepository(client: await _getClient())
      : await SqliteInventoryRepository.create();
  return _inventory!;
}

Future<SalesRepository> getSalesRepository() async {
  if (_sales != null) return _sales!;
  final cfg = await AppConfig.load();
  final inventory = await getInventoryRepository();
  _sales = cfg.onlineMode
      ? ApiSalesRepository(client: await _getClient(), inventoryRepo: inventory)
      : await SqliteSalesRepository.create(inventory);
  return _sales!;
}

Future<CustomerRepository> getCustomerRepository() async {
  if (_customers != null) return _customers!;
  final cfg = await AppConfig.load();
  _customers = cfg.onlineMode
      ? ApiCustomerRepository(client: await _getClient())
      : await SqliteCustomerRepository.create();
  return _customers!;
}

Future<SupplierRepository> getSupplierRepository() async {
  if (_suppliers != null) return _suppliers!;
  final cfg = await AppConfig.load();
  _suppliers = cfg.onlineMode
      ? ApiSupplierRepository(client: await _getClient())
      : await SqliteSupplierRepository.create();
  return _suppliers!;
}

Future<ExpenseRepository> getExpenseRepository() async {
  if (_expenses != null) return _expenses!;
  final cfg = await AppConfig.load();
  _expenses = cfg.onlineMode
      ? ApiExpenseRepository(client: await _getClient())
      : await SqliteExpenseRepository.create();
  return _expenses!;
}

Future<InstallmentRepository> getInstallmentRepository() async {
  if (_installments != null) return _installments!;
  final cfg = await AppConfig.load();
  _installments = cfg.onlineMode
      ? ApiInstallmentRepository(client: await _getClient())
      : await SqliteInstallmentRepository.create();
  return _installments!;
}

Future<MaintenanceRepository> getMaintenanceRepository() async {
  if (_maintenance != null) return _maintenance!;
  final cfg = await AppConfig.load();
  final inventory = await getInventoryRepository();
  _maintenance = cfg.onlineMode
      ? ApiMaintenanceRepository(client: await _getClient())
      : await SqliteMaintenanceRepository.create(inventory);
  return _maintenance!;
}

/// Call this after toggling Online mode. The app must be restarted
/// (or navigated away and back) for the new repos to take effect.
void resetAllRepositories() {
  _apiClient = null;
  _inventory = null;
  _sales = null;
  _customers = null;
  _suppliers = null;
  _expenses = null;
  _installments = null;
  _maintenance = null;
  AppConfig.invalidateRepositoryCache();
}
