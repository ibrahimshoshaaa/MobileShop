import 'sqlite_wallet_repository.dart';
import 'wallet_repository.dart';

Future<WalletRepository>? _cachedRepositoryFuture;

/// The one place the app asks for "the" wallet repository — same pattern
/// as getSalesRepository/getInventoryRepository/etc.
Future<WalletRepository> getWalletRepository() {
  return _cachedRepositoryFuture ??= SqliteWalletRepository.create();
}

void resetWalletRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
