import 'dart:math';
import '../inventory/local_store.dart';
import '../sync/online_push.dart';
import 'wallet_models.dart';
import 'wallet_repository.dart';

class SqliteWalletRepository implements WalletRepository {
  SqliteWalletRepository._(this._store);
  final LocalStore _store;
  static const _entity = 'wallet_tx';

  static Future<SqliteWalletRepository> create() async {
    final store = await LocalStore.open();
    return SqliteWalletRepository._(store);
  }

  WalletTransaction _toTx(Map<String, dynamic> payload) => WalletTransaction(
        id: payload['id'] as String,
        walletId: payload['wallet_id'] as String,
        type: WalletTxTypeX.fromWireValue(payload['type'] as String),
        amount: (payload['amount'] as num).toDouble(),
        note: payload['note'] as String?,
        createdAt: DateTime.parse(payload['created_at'] as String),
      );

  Map<String, dynamic> _toPayload(WalletTransaction t) => {
        'id': t.id,
        'wallet_id': t.walletId,
        'type': t.type.wireValue,
        'amount': t.amount,
        'note': t.note,
        'created_at': t.createdAt.toIso8601String(),
      };

  Future<List<WalletTransaction>> _all() async {
    final rows = await _store.listRecords(entity: _entity);
    final txs = rows.map((r) => _toTx(r.payload)).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return txs;
  }

  @override
  Future<Map<String, double>> getBalances() async {
    final txs = await _all();
    final balances = {for (final w in BuiltinWallets.all) w.id: 0.0};
    for (final t in txs) {
      balances[t.walletId] = (balances[t.walletId] ?? 0) + t.amount;
    }
    return balances;
  }

  @override
  Future<List<WalletTransaction>> listTransactions({String? walletId, int limit = 100}) async {
    final txs = await _all();
    final filtered = walletId == null ? txs : txs.where((t) => t.walletId == walletId).toList();
    return filtered.take(limit).toList(growable: false);
  }

  Future<WalletTransaction> _post({
    required String walletId,
    required double signedAmount,
    required WalletTxType type,
    String? note,
  }) async {
    final tx = WalletTransaction(
      id: _newId(),
      walletId: walletId,
      type: type,
      amount: signedAmount,
      note: (note == null || note.trim().isEmpty) ? null : note.trim(),
      createdAt: DateTime.now(),
    );
    await _store.upsertRecord(entity: _entity, recordId: tx.id, payload: _toPayload(tx), expectedVersion: 0);
    return tx;
  }

  @override
  Future<WalletTransaction> deposit({required String walletId, required double amount, String? note}) async {
    if (amount <= 0) throw WalletException('قيمة الإيداع يجب أن تكون أكبر من صفر.');
    return _postAndSync(walletId: walletId, signedAmount: amount, type: WalletTxType.deposit, note: note);
  }

  @override
  Future<WalletTransaction> withdraw({required String walletId, required double amount, String? note}) async {
    if (amount <= 0) throw WalletException('قيمة السحب يجب أن تكون أكبر من صفر.');
    final balances = await getBalances();
    final current = balances[walletId] ?? 0;
    if (amount > current + 0.01) {
      throw WalletException('الرصيد الحالي (${current.toStringAsFixed(2)}) أقل من قيمة السحب.');
    }
    return _postAndSync(walletId: walletId, signedAmount: -amount, type: WalletTxType.withdraw, note: note);
  }

  /// Manual deposit/withdraw (unlike [postAuto]) has no other server-side
  /// representation — a completed sale/expense/maintenance ticket already
  /// posts its own wallet-side ledger entry when *that* command runs, so
  /// [postAuto]'s local-only record just mirrors something the server
  /// already knows; queuing a command for it too would double the
  /// movement, the same class of bug already fixed for stock adjustments
  /// (see dispatch.py's `_LEGACY_DERIVED_STOCK_REASON`). A manual
  /// deposit/withdrawal has no such command backing it, so it must be
  /// queued and pushed itself, or the local and server balances diverge
  /// for real (report item 7).
  Future<WalletTransaction> _postAndSync({
    required String walletId,
    required double signedAmount,
    required WalletTxType type,
    String? note,
  }) async {
    final tx = await _post(walletId: walletId, signedAmount: signedAmount, type: type, note: note);
    final payload = {'wallet_id': walletId, 'amount': signedAmount, 'reason': note ?? ''};
    await _store.queueCommand(commandId: tx.id, command: 'adjustWallet', payload: payload);
    await pushCommandOnline(_store, tx.id, 'adjustWallet', payload);
    return tx;
  }

  @override
  Future<WalletTransaction> postAuto({
    required String walletId,
    required double signedAmount,
    required WalletTxType type,
    String? note,
  }) {
    return _post(walletId: walletId, signedAmount: signedAmount, type: type, note: note);
  }

  String _newId() => 'wtx-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(999999)}';
}
