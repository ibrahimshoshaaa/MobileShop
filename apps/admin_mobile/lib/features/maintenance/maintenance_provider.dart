import '../inventory/inventory_provider.dart';
import 'maintenance_repository.dart';
import 'sqlite_maintenance_repository.dart';

Future<MaintenanceRepository>? _cachedRepositoryFuture;

Future<MaintenanceRepository> getMaintenanceRepository() {
  return _cachedRepositoryFuture ??= _create();
}

Future<MaintenanceRepository> _create() async {
  final inventory = await getInventoryRepository();
  return SqliteMaintenanceRepository.create(inventory);
}

void resetMaintenanceRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
