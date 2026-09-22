import 'customer_repository.dart';
import 'sqlite_customer_repository.dart';

Future<CustomerRepository>? _cachedRepositoryFuture;

Future<CustomerRepository> getCustomerRepository() {
  return _cachedRepositoryFuture ??= SqliteCustomerRepository.create();
}

void resetCustomerRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
