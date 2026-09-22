import 'package:flutter/material.dart';
import 'reports_models.dart';
import 'reports_provider.dart';
import 'reports_repository.dart';

class ReportsPage extends StatefulWidget {
  const ReportsPage({super.key});

  @override
  State<ReportsPage> createState() => _ReportsPageState();
}

class _ReportsPageState extends State<ReportsPage> {
  late final Future<ReportsRepository> _repositoryFuture;
  ReportsRepository? _repository;
  ReportRangePreset _preset = ReportRangePreset.today;
  late DateRange _range;
  Future<ReportSummary>? _summaryFuture;

  @override
  void initState() {
    super.initState();
    _repositoryFuture = getReportsRepository();
    _range = DateRange.forPreset(_preset);
  }

  void _reload() {
    final repo = _repository;
    if (repo == null) return;
    setState(() => _summaryFuture = repo.buildSummary(_range));
  }

  Future<void> _selectPreset(ReportRangePreset preset) async {
    if (preset == ReportRangePreset.custom) {
      final now = DateTime.now();
      final picked = await showDateRangePicker(
        context: context,
        firstDate: DateTime(now.year - 2),
        lastDate: now,
        initialDateRange: DateTimeRange(start: _range.start, end: _range.lastInclusiveDay),
        locale: const Locale('ar'),
        helpText: 'اختر الفترة',
        cancelText: 'إلغاء',
        confirmText: 'تم',
      );
      if (picked == null) return;
      setState(() {
        _preset = preset;
        _range = DateRange.custom(start: picked.start, end: picked.end);
      });
      _reload();
      return;
    }
    setState(() {
      _preset = preset;
      _range = DateRange.forPreset(preset);
    });
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<ReportsRepository>(
      future: _repositoryFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('تعذّر تحميل التقارير\n${snapshot.error}', textAlign: TextAlign.center));
        }
        _repository = snapshot.data!;
        _summaryFuture ??= _repository!.buildSummary(_range);

        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _RangeFilter(selected: _preset, range: _range, onSelect: _selectPreset),
              const SizedBox(height: 18),
              FutureBuilder<ReportSummary>(
                future: _summaryFuture,
                builder: (context, summarySnapshot) {
                  if (summarySnapshot.connectionState != ConnectionState.done) {
                    return const Padding(
                      padding: EdgeInsets.symmetric(vertical: 40),
                      child: Center(child: CircularProgressIndicator()),
                    );
                  }
                  if (summarySnapshot.hasError) {
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 24),
                      child: Center(
                        child: Text('تعذّر حساب التقرير\n${summarySnapshot.error}', textAlign: TextAlign.center),
                      ),
                    );
                  }
                  return _ReportBody(summary: summarySnapshot.data!);
                },
              ),
            ],
          ),
        );
      },
    );
  }
}

class _RangeFilter extends StatelessWidget {
  const _RangeFilter({required this.selected, required this.range, required this.onSelect});
  final ReportRangePreset selected;
  final DateRange range;
  final void Function(ReportRangePreset) onSelect;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('الفترة', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final preset in ReportRangePreset.values)
                  ChoiceChip(
                    label: Text(preset.label),
                    selected: selected == preset,
                    selectedColor: scheme.primary.withOpacity(0.14),
                    labelStyle: TextStyle(
                      color: selected == preset ? scheme.primary : Colors.black87,
                      fontWeight: selected == preset ? FontWeight.bold : FontWeight.normal,
                    ),
                    onSelected: (_) => onSelect(preset),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              'من ${_formatDay(range.start)} إلى ${_formatDay(range.lastInclusiveDay)}',
              style: const TextStyle(color: Colors.black54, fontSize: 12.5),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReportBody extends StatelessWidget {
  const _ReportBody({required this.summary});
  final ReportSummary summary;

  @override
  Widget build(BuildContext context) {
    final netColor = summary.estimatedNetProfit >= 0 ? const Color(0xFF1B8A4A) : const Color(0xFFC0392B);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _NetProfitCard(summary: summary, color: netColor),
        const SizedBox(height: 14),
        const Text('المبيعات', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 8),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 1.55,
          children: [
            _KpiCard(
              icon: Icons.point_of_sale_rounded,
              label: 'عدد الفواتير',
              value: '${summary.salesCount}',
              color: const Color(0xFF0F3E5C),
            ),
            _KpiCard(
              icon: Icons.payments_rounded,
              label: 'صافي المبيعات',
              value: _money(summary.salesRevenue),
              color: const Color(0xFF0F3E5C),
            ),
            _KpiCard(
              icon: Icons.local_offer_rounded,
              label: 'إجمالي الخصومات',
              value: _money(summary.salesDiscount),
              color: const Color(0xFFB07A1E),
            ),
            _KpiCard(
              icon: Icons.trending_up_rounded,
              label: summary.hasEstimatedCosts ? 'ربح المبيعات (تقديري جزئيًا)' : 'ربح المبيعات',
              value: _money(summary.estimatedGrossProfit),
              color: const Color(0xFF1B8A4A),
              hint: summary.hasEstimatedCosts
                  ? 'بعض فواتير الفترة دي أقدم من ميزة "تكلفة وقت البيع" وبتستخدم تكلفة تقديرية.'
                  : null,
            ),
          ],
        ),
        const SizedBox(height: 18),
        const Text('الصيانة والمصروفات', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 8),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 1.55,
          children: [
            _KpiCard(
              icon: Icons.build_rounded,
              label: 'تذاكر صيانة مُسلّمة',
              value: '${summary.maintenanceDeliveredCount}',
              color: const Color(0xFF0F3E5C),
            ),
            _KpiCard(
              icon: Icons.handyman_rounded,
              label: 'ربح الصيانة',
              value: _money(summary.maintenanceProfit),
              color: const Color(0xFF1B8A4A),
            ),
            _KpiCard(
              icon: Icons.receipt_long_rounded,
              label: 'المصروفات',
              value: _money(summary.expensesTotal),
              color: const Color(0xFFC0392B),
            ),
          ],
        ),
        const SizedBox(height: 18),
        const Text('المخزون الآن', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(height: 8),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 1.55,
          children: [
            _KpiCard(
              icon: Icons.inventory_2_rounded,
              label: 'قيمة المخزون',
              value: _money(summary.inventoryValue),
              color: const Color(0xFF0F3E5C),
              hint: 'لحظة الآن، غير مرتبطة بالفترة المختارة.',
            ),
            _KpiCard(
              icon: Icons.warning_amber_rounded,
              label: 'أصناف تحتاج إعادة طلب',
              value: '${summary.lowStockCount}',
              color: summary.lowStockCount > 0 ? const Color(0xFFC0392B) : const Color(0xFF1B8A4A),
            ),
          ],
        ),
      ],
    );
  }
}

class _NetProfitCard extends StatelessWidget {
  const _NetProfitCard({required this.summary, required this.color});
  final ReportSummary summary;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: color,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(color: Colors.white24, borderRadius: BorderRadius.circular(14)),
              child: const Icon(Icons.account_balance_wallet_rounded, color: Colors.white),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    summary.hasEstimatedCosts ? 'صافي الربح للفترة (تقديري جزئيًا)' : 'صافي الربح للفترة',
                    style: const TextStyle(color: Colors.white70, fontSize: 12.5, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _money(summary.estimatedNetProfit),
                    style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w900),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _KpiCard extends StatelessWidget {
  const _KpiCard({required this.icon, required this.label, required this.value, required this.color, this.hint});
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  final String? hint;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Row(
              children: [
                Icon(icon, size: 18, color: color),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12, color: Colors.black54, fontWeight: FontWeight.w600),
                  ),
                ),
                if (hint != null)
                  Tooltip(
                    message: hint!,
                    child: const Icon(Icons.info_outline_rounded, size: 14, color: Colors.black38),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerRight,
              child: Text(
                value,
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: color),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _formatDay(DateTime d) =>
    '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

String _money(double value) {
  final negative = value < 0;
  final fixed = value.abs().toStringAsFixed(2);
  final dotIndex = fixed.indexOf('.');
  final intPart = fixed.substring(0, dotIndex);
  final decimalPart = fixed.substring(dotIndex);
  final buffer = StringBuffer();
  for (var i = 0; i < intPart.length; i++) {
    if (i > 0 && (intPart.length - i) % 3 == 0) buffer.write(',');
    buffer.write(intPart[i]);
  }
  final formatted = '$buffer$decimalPart ج.م';
  return negative ? '-$formatted' : formatted;
}
