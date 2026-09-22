import 'installment_repository.dart';
import 'sqlite_installment_repository.dart';

Future<InstallmentRepository>? _cachedRepositoryFuture;

Future<InstallmentRepository> getInstallmentRepository() {
  return _cachedRepositoryFuture ??= SqliteInstallmentRepository.create();
}

void resetInstallmentRepositoryForTesting() {
  _cachedRepositoryFuture = null;
}
