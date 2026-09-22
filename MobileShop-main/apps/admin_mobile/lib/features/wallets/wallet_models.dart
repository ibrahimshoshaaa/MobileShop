import 'package:flutter/foundation.dart';

/// The two physical/logical money pools the app tracks a running balance
/// for. Deliberately reuses the same wire values as PaymentMethod
/// (CASH/WALLET) in sale_models.dart so a sale or expense paid by cash or
/// wallet can post straight into the matching ledger without a mapping
/// table. Card settles to a bank account and credit is a receivable, not
/// money on hand, so neither has a wallet balance here.
enum WalletId { cash, wallet }

extension WalletIdX on WalletId {
  String get label => switch (this) {
        WalletId.cash => 'الخزنة (الدرج)',
        WalletId.wallet => 'المحفظة',
      };

  String get wireValue => switch (this) {
        WalletId.cash => 'CASH',
        WalletId.wallet => 'WALLET',
      };

  static WalletId fromWireValue(String value) => switch (value) {
        'CASH' => WalletId.cash,
        'WALLET' => WalletId.wallet,
        _ => throw ArgumentError('Unknown WalletId wire value: $value'),
      };

  /// Returns null (instead of throwing) for wire values that don't have a
  /// wallet balance (CARD/CREDIT) — the convenience callers that post from
  /// a PaymentMethod need, since not every payment line should touch a
  /// wallet ledger.
  static WalletId? tryFromWireValue(String value) => switch (value) {
        'CASH' => WalletId.cash,
        'WALLET' => WalletId.wallet,
        _ => null,
      };
}

/// What kind of event moved money in/out of a wallet.
enum WalletTxType { deposit, withdraw, sale, expense, maintenance, adjustment }

extension WalletTxTypeX on WalletTxType {
  String get label => switch (this) {
        WalletTxType.deposit => 'إيداع',
        WalletTxType.withdraw => 'سحب',
        WalletTxType.sale => 'تحصيل فاتورة بيع',
        WalletTxType.expense => 'مصروف',
        WalletTxType.maintenance => 'تحصيل صيانة',
        WalletTxType.adjustment => 'تسوية',
      };

  String get wireValue => name.toUpperCase();

  static WalletTxType fromWireValue(String value) =>
      WalletTxType.values.firstWhere((t) => t.wireValue == value);
}

@immutable
class WalletTransaction {
  final String id;
  final WalletId walletId;
  final WalletTxType type;

  /// Signed amount — positive for money in, negative for money out.
  final double amount;
  final String? note;
  final DateTime createdAt;

  const WalletTransaction({
    required this.id,
    required this.walletId,
    required this.type,
    required this.amount,
    this.note,
    required this.createdAt,
  });
}

class WalletException implements Exception {
  final String message;
  WalletException(this.message);
  @override
  String toString() => message;
}
