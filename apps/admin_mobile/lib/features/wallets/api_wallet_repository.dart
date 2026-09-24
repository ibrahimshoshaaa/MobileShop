import '../sync/api_client.dart';
import 'wallet_models.dart';
import 'wallet_repository.dart';

/// Server-backed [WalletRepository] — 4.2 ("قراءة البيانات ... من
/// السيرفر"). Unlike inventory/customers/suppliers, the server has no
/// wallet-transaction table shaped like the mobile app's local `wallet_tx`
/// — wallets are money-movement *accounts* there, and every movement is a
/// double-entry row in the ledger (`shared/models/erp.py:LedgerEntry`:
/// `account_id`, `debit`, `credit`), read via `GET /query/ledger`.
///
/// [getBalances] mirrors the server's own formula exactly —
/// `backend/functions/accounting/service.py:AccountingService.balance()`
/// is `sum(debit - credit)` for a given `account_id` — applied to entries
/// whose `account_id` is `wallet:<walletId>` (that prefix is how
/// `backend/functions/services/completion.py` tags every wallet-side
/// posting, e.g. `wallet:wallet-cash`).
///
/// [listTransactions] turns each matching ledger row into a
/// [WalletTransaction] for display. The ledger `entry_type`s that map onto
/// a [WalletTxType] the mobile app already has a concept of are
/// `SALE_PAYMENT`, `MAINTENANCE_PAYMENT`, and `INSTALLMENT_DOWN_PAYMENT`/
/// `INSTALLMENT_PAYMENT`; everything else the server can post against a
/// wallet (`PURCHASE_PAYMENT`, `CUSTOMER_PAYMENT`, `CUSTOMER_TRANSFER_IN`/
/// `OUT`) has no mobile-side feature behind it yet (purchases, standalone
/// customer collection, wallet-to-wallet transfer), so those fall back to
/// [WalletTxType.adjustment] with the original server entry type kept in
/// [WalletTransaction.note] rather than mislabeling them — see
/// [_mapEntryType].
///
/// Deposits/withdrawals ([deposit], [withdraw]) write to [_local] first
/// (so the UI updates immediately, offline-first) and are then queued and
/// pushed to the server as `adjustWallet` — see
/// [SqliteWalletRepository._postAndSync]. Automatic postings from a
/// completed local sale/expense/maintenance ticket ([postAuto]) stay
/// local-only: that command already posted its own wallet-side ledger
/// entry on the server, so pushing [postAuto] too would double the
/// movement.
class ApiWalletRepository implements WalletRepository {
  ApiWalletRepository(this._client, this._local);

  final ApiClient _client;
  final WalletRepository _local;

  static const _accountPrefix = 'wallet:';

  Future<List<Map<String, dynamic>>> _ledgerEntries() => _client.getEntity('ledger', limit: 500);

  WalletTxType _mapEntryType(String entryType) => switch (entryType) {
        'SALE_PAYMENT' => WalletTxType.sale,
        'MAINTENANCE_PAYMENT' => WalletTxType.maintenance,
        'INSTALLMENT_DOWN_PAYMENT' || 'INSTALLMENT_PAYMENT' => WalletTxType.installment,
        _ => WalletTxType.adjustment,
      };

  @override
  Future<Map<String, double>> getBalances() async {
    final List<Map<String, dynamic>> entries;
    try {
      entries = await _ledgerEntries();
    } on ApiException catch (e) {
      throw WalletException(e.message);
    }
    final balances = {for (final w in BuiltinWallets.all) w.id: 0.0};
    for (final e in entries) {
      final accountId = e['account_id'] as String? ?? '';
      if (!accountId.startsWith(_accountPrefix)) continue;
      final walletId = accountId.substring(_accountPrefix.length);
      if (!balances.containsKey(walletId)) continue; // wallet the mobile app doesn't know about yet
      final debit = double.tryParse('${e['debit']}') ?? 0;
      final credit = double.tryParse('${e['credit']}') ?? 0;
      balances[walletId] = (balances[walletId] ?? 0) + (debit - credit);
    }
    return balances;
  }

  @override
  Future<List<WalletTransaction>> listTransactions({String? walletId, int limit = 100}) async {
    final List<Map<String, dynamic>> entries;
    try {
      entries = await _ledgerEntries();
    } on ApiException catch (e) {
      throw WalletException(e.message);
    }
    final txs = <WalletTransaction>[];
    for (final e in entries) {
      final accountId = e['account_id'] as String? ?? '';
      if (!accountId.startsWith(_accountPrefix)) continue;
      final entryWalletId = accountId.substring(_accountPrefix.length);
      if (walletId != null && entryWalletId != walletId) continue;
      final debit = double.tryParse('${e['debit']}') ?? 0;
      final credit = double.tryParse('${e['credit']}') ?? 0;
      final entryType = e['entry_type'] as String? ?? '';
      final mapped = _mapEntryType(entryType);
      txs.add(WalletTransaction(
        id: e['id'] as String,
        walletId: entryWalletId,
        type: mapped,
        amount: debit - credit,
        note: mapped == WalletTxType.adjustment ? entryType : null,
        createdAt: DateTime.tryParse('${e['created_at']}') ?? DateTime.now(),
      ));
    }
    txs.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return txs.take(limit).toList(growable: false);
  }

  @override
  Future<WalletTransaction> deposit({required String walletId, required double amount, String? note}) =>
      _local.deposit(walletId: walletId, amount: amount, note: note);

  @override
  Future<WalletTransaction> withdraw({required String walletId, required double amount, String? note}) =>
      _local.withdraw(walletId: walletId, amount: amount, note: note);

  @override
  Future<WalletTransaction> postAuto({
    required String walletId,
    required double signedAmount,
    required WalletTxType type,
    String? note,
  }) =>
      _local.postAuto(walletId: walletId, signedAmount: signedAmount, type: type, note: note);
}
