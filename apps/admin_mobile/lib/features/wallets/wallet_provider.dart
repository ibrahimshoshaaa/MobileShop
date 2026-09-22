import '../auth/auth_service.dart';
import '../sync/api_client.dart';
import 'api_wallet_repository.dart';
import 'sqlite_wallet_repository.dart';
import 'wallet_repository.dart';

Future<WalletRepository>? _cachedRepositoryFuture;

/// The one place the app asks for "the" wallet repository — same pattern
/// as getSalesRepository/getInventoryRepository/etc. Balances/transactions
/// come from the server (4.2) whenever [AuthService] has an active
/// session; [deposit]/[withdraw]/[postAuto] always go to the local SQLite
/// repository regardless (see [ApiWalletRepository]'s doc comment), which
/// is exactly what keeps sale/expense/maintenance completion — every one of
/// which calls this function to post an automatic wallet entry — working
/// unchanged whether the returned repository is the online or offline one.
Future<WalletRepository> getWalletRepository() async {
  final local = await (_cachedRepositoryFuture ??= SqliteWalletRepository.create());
  final session = AuthService.instance.currentSession;
  if (session == null) return local;
  return ApiWalletRepository(ApiClient.fromSession(session), local);
}

void resetWalletRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
