import 'wallet_models.dart';

/// Abstraction the UI (and the sale/expense/maintenance repositories, which
/// post automatic entries) depend on. Mirrors the same "local ledger today,
/// server-authoritative ledger once the backend wallet/ledger commands ship"
/// pattern already used across inventory/sales/installments in this app.
abstract class WalletRepository {
  /// Current balance per wallet, computed from the transaction ledger.
  Future<Map<WalletId, double>> getBalances();

  Future<List<WalletTransaction>> listTransactions({WalletId? walletId, int limit = 100});

  Future<WalletTransaction> deposit({required WalletId walletId, required double amount, String? note});

  Future<WalletTransaction> withdraw({required WalletId walletId, required double amount, String? note});

  /// Used internally by other repositories (sales/expenses/maintenance) to
  /// post an automatic, signed entry — never exposed as a raw "post
  /// anything" action from the UI, which only ever calls deposit/withdraw.
  Future<WalletTransaction> postAuto({
    required WalletId walletId,
    required double signedAmount,
    required WalletTxType type,
    String? note,
  });
}
