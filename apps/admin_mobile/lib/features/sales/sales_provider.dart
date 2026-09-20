import '../inventory/inventory_provider.dart';
import 'sale_repository.dart';
import 'sqlite_sale_repository.dart';

Future<SalesRepository>? _cachedRepositoryFuture;

/// The one place the app asks for "the" sales repository.
Future<SalesRepository> getSalesRepository() {
  return _cachedRepositoryFuture ??= _create();
}

Future<SalesRepository> _create() async {
  final inventory = await getInventoryRepository();
  return SqliteSalesRepository.create(inventory);
}

void resetSalesRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
