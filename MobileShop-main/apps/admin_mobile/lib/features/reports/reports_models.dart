import 'package:flutter/foundation.dart';

/// Quick date-range presets shown as filter chips on the reports screen.
enum ReportRangePreset { today, last7Days, thisMonth, custom }

extension ReportRangePresetX on ReportRangePreset {
  String get label => switch (this) {
        ReportRangePreset.today => 'اليوم',
        ReportRangePreset.last7Days => 'آخر 7 أيام',
        ReportRangePreset.thisMonth => 'هذا الشهر',
        ReportRangePreset.custom => 'مخصص',
      };
}

/// A half-open date window: [start, end) — start inclusive, end exclusive,
/// both at midnight, so a whole calendar day is included by using the next
/// day's midnight as `end`.
@immutable
class DateRange {
  final DateTime start;
  final DateTime end;
  const DateRange({required this.start, required this.end});

  static DateTime _startOfDay(DateTime d) => DateTime(d.year, d.month, d.day);

  factory DateRange.forPreset(ReportRangePreset preset, {DateTime? now}) {
    final today = _startOfDay(now ?? DateTime.now());
    final tomorrow = today.add(const Duration(days: 1));
    switch (preset) {
      case ReportRangePreset.today:
        return DateRange(start: today, end: tomorrow);
      case ReportRangePreset.last7Days:
        return DateRange(start: today.subtract(const Duration(days: 6)), end: tomorrow);
      case ReportRangePreset.thisMonth:
        return DateRange(start: DateTime(today.year, today.month, 1), end: tomorrow);
      case ReportRangePreset.custom:
        // Caller replaces start/end right after; today is a harmless default.
        return DateRange(start: today, end: tomorrow);
    }
  }

  factory DateRange.custom({required DateTime start, required DateTime end}) {
    // Normalise to whole days and make `end` exclusive of the day after it,
    // so a user picking "from 1 to 5" gets all of the 5th included.
    final s = _startOfDay(start);
    final e = _startOfDay(end).add(const Duration(days: 1));
    return DateRange(start: s, end: e);
  }

  bool contains(DateTime dt) => !dt.isBefore(start) && dt.isBefore(end);

  /// Inclusive last day, for display (end is exclusive/midnight so it would
  /// otherwise print as the day after what the user picked).
  DateTime get lastInclusiveDay => end.subtract(const Duration(days: 1));
}

/// Aggregated numbers for one [DateRange], pulled from sales, expenses and
/// maintenance, plus a current (not date-bound) inventory snapshot.
///
/// Note on accuracy: since plan item 1.4, `estimatedCogs` is built from each
/// sale item's own [SaleItemRecord.costAtSale] — the cost snapshotted at the
/// moment that item was actually sold — rather than the product's current
/// cost. That makes it exact for any sale made from 1.4 onward. The only
/// remaining source of estimation is sales made *before* 1.4 existed, whose
/// items were backfilled by a one-time migration using the cost at
/// migration time (the real historical cost was never recorded for those).
/// [hasEstimatedCosts] is true when the selected range includes at least one
/// such backfilled item, so the UI can keep showing "تقديري" only when it's
/// actually still an estimate. Maintenance profit never had this problem —
/// [MaintenanceTicket.partsCost] is already recorded at the time parts were
/// used.
@immutable
class ReportSummary {
  final DateRange range;

  final int salesCount;
  final double salesRevenue;
  final double salesDiscount;
  final double estimatedCogs;
  final bool hasEstimatedCosts;

  final double expensesTotal;

  final int maintenanceDeliveredCount;
  final double maintenanceRevenue;
  final double maintenancePartsCost;

  final double inventoryValue;
  final int lowStockCount;

  const ReportSummary({
    required this.range,
    required this.salesCount,
    required this.salesRevenue,
    required this.salesDiscount,
    required this.estimatedCogs,
    required this.hasEstimatedCosts,
    required this.expensesTotal,
    required this.maintenanceDeliveredCount,
    required this.maintenanceRevenue,
    required this.maintenancePartsCost,
    required this.inventoryValue,
    required this.lowStockCount,
  });

  double get estimatedGrossProfit => salesRevenue - estimatedCogs;
  double get maintenanceProfit => maintenanceRevenue - maintenancePartsCost;

  /// Best-effort net profit for the period: gross profit from sales, plus
  /// maintenance profit, minus operating expenses. Inherits the same
  /// [hasEstimatedCosts] caveat as [estimatedGrossProfit].
  double get estimatedNetProfit => estimatedGrossProfit + maintenanceProfit - expensesTotal;
}
