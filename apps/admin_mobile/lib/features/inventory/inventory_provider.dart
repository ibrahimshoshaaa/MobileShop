import '../auth/auth_service.dart';
import '../sync/api_client.dart';
import 'api_inventory_repository.dart';
import 'inventory_repository.dart';
import 'sqlite_inventory_repository.dart';

Future<InventoryRepository>? _cachedRepositoryFuture;

/// The one place the app asks for "the" inventory repository. Always backed
/// by SQLite underneath (data survives app restarts, and every write — even
/// in online mode — still lands there for now, see [ApiInventoryRepository]).
/// The *list* returned to callers comes from the server instead (4.2) when
/// [AuthService] has an active session; otherwise it's the same offline
/// repository as before. The session is re-checked on every call rather
/// than baked into the cached future, so logging in/out takes effect on the
/// next read without needing an app restart.
Future<InventoryRepository> getInventoryRepository() async {
  final local = await (_cachedRepositoryFuture ??= SqliteInventoryRepository.create());
  final session = AuthService.instance.currentSession;
  if (session == null) return local;
  return ApiInventoryRepository(ApiClient.fromSession(session), local);
}

/// Clears the cached instance — useful for widget tests that want a fresh
/// repository per test.
void resetInventoryRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
