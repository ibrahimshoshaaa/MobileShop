import '../auth/auth_service.dart';
import '../sync/api_client.dart';
import 'api_supplier_repository.dart';
import 'sqlite_supplier_repository.dart';
import 'supplier_repository.dart';

Future<SupplierRepository>? _cachedRepositoryFuture;

/// Same pattern as [getInventoryRepository]: the offline SQLite repository
/// stays the one thing every write goes to, but reads come from the server
/// (4.2) whenever [AuthService] has an active session.
Future<SupplierRepository> getSupplierRepository() async {
  final local = await (_cachedRepositoryFuture ??= SqliteSupplierRepository.create());
  final session = AuthService.instance.currentSession;
  if (session == null) return local;
  return ApiSupplierRepository(ApiClient.fromSession(session), local);
}

void resetSupplierRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
