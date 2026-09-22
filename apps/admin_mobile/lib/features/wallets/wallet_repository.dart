import 'wallet_models.dart';

/// Abstraction the UI (and the sale/expense/maintenance repositories, which
/// post automatic entries) depend on. Mirrors the same "local ledger today,
/// server-authoritative ledger once the backend wallet/ledger commands ship"
/// pattern already used across inventory/sales/installments in this app.
///
/// Wallets are referenced by [Wallet.id] (a plain string) rather than the
/// old `WalletId` enum, so a future synced wallet list can add wallets
/// beyond [BuiltinWallets] without changing this interface.
abstract class WalletRepository {
  /// Current balance per wallet id, computed from the transaction ledger.
  Future<Map<String, double>> getBalances();

  Future<List<WalletTransaction>> listTransactions({String? walletId, int limit = 100});

  Future<WalletTransaction> deposit({required String walletId, required double amount, String? note});

  Future<WalletTransaction> withdraw({required String walletId, required double amount, String? note});

  /// Used internally by other repositories (sales/expenses/maintenance) to
  /// post an automatic, signed entry — never exposed as a raw "post
  /// anything" action from the UI, which only ever calls deposit/withdraw.
  Future<WalletTransaction> postAuto({
    required String walletId,
    required double signedAmount,
    required WalletTxType type,
    String? note,
  });
}
