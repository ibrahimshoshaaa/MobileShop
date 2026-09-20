import 'inventory_repository.dart';
import 'sqlite_inventory_repository.dart';

Future<InventoryRepository>? _cachedRepositoryFuture;

/// The one place the app asks for "the" inventory repository. Backed by
/// SQLite so data survives app restarts; swap the implementation here if a
/// remote/API-backed repository is added later.
Future<InventoryRepository> getInventoryRepository() {
  return _cachedRepositoryFuture ??= SqliteInventoryRepository.create();
}

/// Clears the cached instance — useful for widget tests that want a fresh
/// repository per test.
void resetInventoryRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
