import 'sqlite_supplier_repository.dart';
import 'supplier_repository.dart';

Future<SupplierRepository>? _cachedRepositoryFuture;

Future<SupplierRepository> getSupplierRepository() {
  return _cachedRepositoryFuture ??= SqliteSupplierRepository.create();
}

void resetSupplierRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
