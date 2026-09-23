import 'package:flutter/foundation.dart';
import '../inventory/local_store.dart';

/// A wallet — a physical/logical money pool with a running balance.
///
/// Mirrors the backend's `Wallet` model (shared/models/erp.py:
/// `{id, branch_id, name, wallet_type, active, tenant_id}`) instead of the
/// old fixed `WalletId` enum, so the local shape matches the server's once
/// sync ships (PLAN.md, phase 2.1). For now the app only ever works with
/// the two [BuiltinWallets] below — real multi-wallet CRUD (custom wallets
/// per branch) is out of scope until the backend wallet list is synced in.
@immutable
class Wallet {
  final String id;
  final String branchId;
  final String name;
  final String walletType;
  final bool active;

  const Wallet({
    required this.id,
    required this.branchId,
    required this.name,
    required this.walletType,
    this.active = true,
  });

  /// The wire value used on `PaymentMethod` (CASH/WALLET) and stored on
  /// wallet transaction payloads — same role `WalletId.wireValue` played
  /// before. Built-in wallets deliberately reuse their `walletType` as this
  /// value so a sale/expense paid by cash or wallet can post straight into
  /// the matching ledger without a mapping table. Card settles to a bank
  /// account and credit is a receivable, not money on hand, so neither has
  /// a wallet here.
  String get wireValue => walletType;

  String get label => name;

  @override
  bool operator ==(Object other) => other is Wallet && other.id == id;

  @override
  int get hashCode => id.hashCode;
}

/// The two wallets every branch starts with today. Once wallet CRUD +
/// sync exist (phase 4/5), these become the seed data for a real
/// per-branch wallet list instead of the only wallets that can ever exist.
class BuiltinWallets {
  const BuiltinWallets._();

  static const cash = Wallet(
    id: 'wallet-cash',
    branchId: LocalStore.defaultBranchId,
    name: 'الخزنة (الدرج)',
    walletType: 'CASH',
  );

  static const wallet = Wallet(
    id: 'wallet-wallet',
    branchId: LocalStore.defaultBranchId,
    name: 'المحفظة',
    walletType: 'WALLET',
  );

  static const all = [cash, wallet];

  static Wallet byId(String id) => all.firstWhere(
        (w) => w.id == id,
        orElse: () => throw ArgumentError('Unknown wallet id: $id'),
      );

  static Wallet fromWireValue(String value) => all.firstWhere(
        (w) => w.wireValue == value,
        orElse: () => throw ArgumentError('Unknown wallet wire value: $value'),
      );

  /// Returns null (instead of throwing) for wire values that don't have a
  /// wallet balance (CARD/CREDIT) — the convenience callers that post from
  /// a PaymentMethod need, since not every payment line should touch a
  /// wallet ledger.
  static Wallet? tryFromWireValue(String value) {
    for (final w in all) {
      if (w.wireValue == value) return w;
    }
    return null;
  }
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

  /// The owning wallet's [Wallet.id] — was a `WalletId` enum value before
  /// phase 2.1, now a plain id so it can reference any wallet, not just the
  /// two built-ins.
  final String walletId;
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

/// The wallet reference the SERVER understands for a payment method, or null
/// when that method has no wallet on the server (credit = an on-account
/// receivable). Cash/wallet map to the built-in wallets; card maps to the
/// branch's card/bank wallet. The server resolves these fixed names to the
/// branch's real wallets (creating them on first use), so the app never has to
/// create wallets itself. Card settles to a bank account, so it is only sent
/// for money coming IN (sales, maintenance delivery, installment collection) —
/// the local wallet ledger deliberately still skips it (see BuiltinWallets).
String? serverWalletRefForMethod(String wireValue) =>
    BuiltinWallets.tryFromWireValue(wireValue)?.id ?? (wireValue == 'CARD' ? 'wallet-card' : null);
