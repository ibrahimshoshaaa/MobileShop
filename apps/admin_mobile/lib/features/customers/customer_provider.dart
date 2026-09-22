import '../auth/auth_service.dart';
import '../sync/api_client.dart';
import 'api_customer_repository.dart';
import 'customer_repository.dart';
import 'sqlite_customer_repository.dart';

Future<CustomerRepository>? _cachedRepositoryFuture;

/// Same pattern as [getInventoryRepository]: the offline SQLite repository
/// stays the one thing every write goes to, but reads come from the server
/// (4.2) whenever [AuthService] has an active session.
Future<CustomerRepository> getCustomerRepository() async {
  final local = await (_cachedRepositoryFuture ??= SqliteCustomerRepository.create());
  final session = AuthService.instance.currentSession;
  if (session == null) return local;
  return ApiCustomerRepository(ApiClient.fromSession(session), local);
}

void resetCustomerRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
