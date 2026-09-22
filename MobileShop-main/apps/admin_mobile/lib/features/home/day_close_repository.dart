import 'package:flutter/foundation.dart';
import '../inventory/local_store.dart';

/// A snapshot of one day's totals, taken when the day is closed. This app
/// has no server-side day-close command yet (see the wallet/ledger
/// simplification note in expense_models.dart) — closing a day here just
/// records the snapshot locally so it can't be silently re-closed, and
/// gives the operator a receipt-style summary to check against the drawer.
@immutable
class DayCloseSummary {
  final String dateKey; // yyyy-MM-dd
  final double salesTotal;
  final int salesCount;
  final double expensesTotal;
  final double netProfit;
  final double cashBalance;
  final double walletBalance;
  final DateTime closedAt;

  const DayCloseSummary({
    required this.dateKey,
    required this.salesTotal,
    required this.salesCount,
    required this.expensesTotal,
    required this.netProfit,
    required this.cashBalance,
    required this.walletBalance,
    required this.closedAt,
  });
}

class DayCloseRepository {
  DayCloseRepository._(this._store);
  final LocalStore _store;
  static const _entity = 'day_close';

  static Future<DayCloseRepository> create() async {
    final store = await LocalStore.open();
    return DayCloseRepository._(store);
  }

  String _keyFor(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';

  Future<DayCloseSummary?> getForToday() async {
    final key = _keyFor(DateTime.now());
    final record = await _store.getRecord(entity: _entity, recordId: key);
    if (record == null) return null;
    final p = record.payload;
    return DayCloseSummary(
      dateKey: key,
      salesTotal: (p['sales_total'] as num).toDouble(),
      salesCount: p['sales_count'] as int,
      expensesTotal: (p['expenses_total'] as num).toDouble(),
      netProfit: (p['net_profit'] as num).toDouble(),
      cashBalance: (p['cash_balance'] as num).toDouble(),
      walletBalance: (p['wallet_balance'] as num).toDouble(),
      closedAt: DateTime.parse(p['closed_at'] as String),
    );
  }

  Future<DayCloseSummary> closeToday({
    required double salesTotal,
    required int salesCount,
    required double expensesTotal,
    required double netProfit,
    required double cashBalance,
    required double walletBalance,
  }) async {
    final key = _keyFor(DateTime.now());
    final closedAt = DateTime.now();
    await _store.upsertRecord(
      entity: _entity,
      recordId: key,
      payload: {
        'sales_total': salesTotal,
        'sales_count': salesCount,
        'expenses_total': expensesTotal,
        'net_profit': netProfit,
        'cash_balance': cashBalance,
        'wallet_balance': walletBalance,
        'closed_at': closedAt.toIso8601String(),
      },
      expectedVersion: 0,
    );
    return DayCloseSummary(
      dateKey: key,
      salesTotal: salesTotal,
      salesCount: salesCount,
      expensesTotal: expensesTotal,
      netProfit: netProfit,
      cashBalance: cashBalance,
      walletBalance: walletBalance,
      closedAt: closedAt,
    );
  }
}
