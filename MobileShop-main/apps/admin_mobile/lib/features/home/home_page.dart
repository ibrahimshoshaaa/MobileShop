import 'package:flutter/material.dart';
import '../expenses/expense_models.dart';
import '../expenses/expense_provider.dart';
import '../expenses/expense_repository.dart';
import '../expenses/expenses_page.dart' show ExpenseFormSheet;
import '../inventory/inventory_models.dart';
import '../inventory/inventory_page.dart' show ProductListScreen;
import '../inventory/inventory_provider.dart';
import '../inventory/inventory_repository.dart';
import '../maintenance/maintenance_models.dart';
import '../maintenance/maintenance_page.dart' show NewTicketScreen;
import '../maintenance/maintenance_provider.dart';
import '../maintenance/maintenance_repository.dart';
import '../sales/sale_models.dart';
import '../sales/sales_page.dart' show NewSaleScreen, SaleDetailScreen;
import '../sales/sales_provider.dart';
import '../sales/sale_repository.dart';
import '../wallets/wallet_models.dart';
import '../wallets/wallet_provider.dart';
import '../wallets/wallet_repository.dart';
import '../wallets/wallets_page.dart' show WalletTxSheet;
import 'day_close_repository.dart';

const navy = Color(0xFF0F3E5C);
const pageBg = Color(0xFFF4F5F9);

class HomePage extends StatefulWidget {
  const HomePage({super.key, required this.onOpenMenu, required this.onGoToWallets});
  final VoidCallback onOpenMenu;
  final VoidCallback onGoToWallets;

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomeData {
  final double netProfitToday;
  final double salesTotalToday;
  final int salesCountToday;
  final double expensesTotalToday;
  final double cashBalance;
  final double walletBalance;
  final double customerDebt;
  final int maintenanceOpenCount;
  final List<_RecentOp> recentOps;

  _HomeData({
    required this.netProfitToday,
    required this.salesTotalToday,
    required this.salesCountToday,
    required this.expensesTotalToday,
    required this.cashBalance,
    required this.walletBalance,
    required this.customerDebt,
    required this.maintenanceOpenCount,
    required this.recentOps,
  });
}

class _RecentOp {
  final IconData icon;
  final String title;
  final String subtitle;
  final double amount;
  final DateTime at;
  final SaleRecord? sale;
  _RecentOp({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.amount,
    required this.at,
    this.sale,
  });
}

class _HomePageState extends State<HomePage> {
  SalesRepository? _salesRepo;
  ExpenseRepository? _expenseRepo;
  MaintenanceRepository? _maintenanceRepo;
  InventoryRepository? _inventoryRepo;
  WalletRepository? _walletRepo;
  Future<_HomeData>? _dataFuture;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final future = _computeData();
    setState(() => _dataFuture = future);
  }

  Future<_HomeData> _computeData() async {
    _salesRepo ??= await getSalesRepository();
    _expenseRepo ??= await getExpenseRepository();
    _maintenanceRepo ??= await getMaintenanceRepository();
    _inventoryRepo ??= await getInventoryRepository();
    _walletRepo ??= await getWalletRepository();

    final now = DateTime.now();
    final startOfDay = DateTime(now.year, now.month, now.day);

    final results = await Future.wait([
      _salesRepo!.listRecentSales(limit: 500),
      _expenseRepo!.listExpenses(from: startOfDay),
      _maintenanceRepo!.listTickets(),
      _inventoryRepo!.listProducts(),
      _walletRepo!.getBalances(),
    ]);
    final allSales = results[0] as List<SaleRecord>;
    final expensesToday = results[1] as List<Expense>;
    final tickets = results[2] as List<MaintenanceTicket>;
    final products = results[3] as List<Product>;
    final balances = results[4] as Map<WalletId, double>;

    final costById = {for (final p in products) p.id: p.defaultCost};

    final salesToday = allSales
        .where((s) => s.status == 'COMPLETED' && !s.createdAt.isBefore(startOfDay))
        .toList();

    double grossProfitToday = 0;
    for (final s in salesToday) {
      for (final item in s.items) {
        final cost = costById[item.productId] ?? 0;
        grossProfitToday += (item.unitPrice - cost) * item.quantity;
      }
    }
    final expensesTotalToday = expensesToday.fold<double>(0, (sum, e) => sum + e.amount);
    final netProfitToday = grossProfitToday - expensesTotalToday;
    final salesTotalToday = salesToday.fold<double>(0, (sum, s) => sum + s.total);

    double customerDebt = 0;
    for (final s in allSales) {
      if (s.status != 'COMPLETED' || s.customerId == null) continue;
      final paid = s.payments.fold<double>(0, (sum, p) => sum + p.amount);
      final due = s.total - paid;
      if (due > 0.01) customerDebt += due;
    }

    final maintenanceOpenCount = tickets.where((t) => t.isOpen).length;

    final recentOps = <_RecentOp>[
      ...salesToday.map((s) => _RecentOp(
            icon: Icons.point_of_sale_rounded,
            title: 'فاتورة بيع ${s.customerName != null ? '- ${s.customerName}' : ''}',
            subtitle: '${s.items.length} صنف',
            amount: s.total,
            at: s.createdAt,
            sale: s,
          )),
      ...expensesToday.map((e) => _RecentOp(
            icon: Icons.receipt_long_rounded,
            title: 'مصروف - ${e.category}',
            subtitle: e.note ?? e.method.label,
            amount: -e.amount,
            at: e.createdAt,
          )),
    ]..sort((a, b) => b.at.compareTo(a.at));

    return _HomeData(
      netProfitToday: netProfitToday,
      salesTotalToday: salesTotalToday,
      salesCountToday: salesToday.length,
      expensesTotalToday: expensesTotalToday,
      cashBalance: balances[WalletId.cash] ?? 0,
      walletBalance: balances[WalletId.wallet] ?? 0,
      customerDebt: customerDebt,
      maintenanceOpenCount: maintenanceOpenCount,
      recentOps: recentOps.take(8).toList(),
    );
  }

  Future<void> _openNewSale() async {
    final navigator = Navigator.of(context);
    final repo = _salesRepo ?? await getSalesRepository();
    if (!mounted) return;
    final created = await navigator.push<bool>(
      MaterialPageRoute(builder: (_) => NewSaleScreen(repository: repo)),
    );
    if (created == true) _load();
  }

  Future<void> _openNewMaintenanceTicket() async {
    final repo = _maintenanceRepo ?? await getMaintenanceRepository();
    if (!mounted) return;
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => NewTicketScreen(repository: repo)),
    );
    if (created == true) _load();
  }

  Future<void> _openBuyUsedPhone() async {
    final repo = _inventoryRepo ?? await getInventoryRepository();
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ProductListScreen(repository: repo, type: ProductType.phoneUsed)),
    );
    _load();
  }

  Future<void> _openBuyGoods() async {
    final repo = _inventoryRepo ?? await getInventoryRepository();
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ProductListScreen(repository: repo, type: null)),
    );
    _load();
  }

  Future<void> _openRecordExpense() async {
    final repo = _expenseRepo ?? await getExpenseRepository();
    if (!mounted) return;
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (_) => ExpenseFormSheet(repository: repo),
    );
    if (added == true) _load();
  }

  Future<void> _openSearch() async {
    final repo = _inventoryRepo ?? await getInventoryRepository();
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ProductListScreen(repository: repo, type: null)),
    );
  }

  Future<void> _closeDay(_HomeData data) async {
    final dayCloseRepo = await DayCloseRepository.create();
    final existing = await dayCloseRepo.getForToday();
    if (!mounted) return;
    if (existing != null) {
      await _showDayCloseSummary(existing, alreadyClosed: true);
      return;
    }
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('تقفيل اليوم'),
        content: Text(
          'صافي ربح اليوم: ${data.netProfitToday.toStringAsFixed(0)} ج.م\n'
          'مبيعات اليوم: ${data.salesTotalToday.toStringAsFixed(0)} ج.م (${data.salesCountToday} فاتورة)\n'
          'رصيد الخزنة الحالي: ${data.cashBalance.toStringAsFixed(0)} ج.م\n\n'
          'هل تريد تقفيل اليوم وحفظ هذا الملخص؟',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('إلغاء')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('تقفيل')),
        ],
      ),
    );
    if (confirm != true) return;
    final summary = await dayCloseRepo.closeToday(
      salesTotal: data.salesTotalToday,
      salesCount: data.salesCountToday,
      expensesTotal: data.expensesTotalToday,
      netProfit: data.netProfitToday,
      cashBalance: data.cashBalance,
      walletBalance: data.walletBalance,
    );
    if (!mounted) return;
    await _showDayCloseSummary(summary, alreadyClosed: false);
  }

  Future<void> _showDayCloseSummary(DayCloseSummary summary, {required bool alreadyClosed}) {
    return showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(alreadyClosed ? 'تم تقفيل اليوم بالفعل' : 'تم تقفيل اليوم'),
        content: Text(
          'وقت التقفيل: ${summary.closedAt.hour.toString().padLeft(2, '0')}:${summary.closedAt.minute.toString().padLeft(2, '0')}\n'
          'صافي الربح: ${summary.netProfit.toStringAsFixed(0)} ج.م\n'
          'مبيعات اليوم: ${summary.salesTotal.toStringAsFixed(0)} ج.م (${summary.salesCount} فاتورة)\n'
          'رصيد الخزنة: ${summary.cashBalance.toStringAsFixed(0)} ج.م\n'
          'رصيد المحفظة: ${summary.walletBalance.toStringAsFixed(0)} ج.م',
        ),
        actions: [FilledButton(onPressed: () => Navigator.pop(context), child: const Text('تمام'))],
      ),
    );
  }

  Future<void> _openWalletChoice() async {
    final repo = _walletRepo ?? await getWalletRepository();
    if (!mounted) return;
    final action = await showModalBottomSheet<String>(
      context: context,
      builder: (_) => SafeArea(
        child: Wrap(children: [
          ListTile(
            leading: const Icon(Icons.add_circle_outline),
            title: const Text('إيداع في محفظة'),
            onTap: () => Navigator.pop(context, 'deposit'),
          ),
          ListTile(
            leading: const Icon(Icons.remove_circle_outline),
            title: const Text('سحب من محفظة'),
            onTap: () => Navigator.pop(context, 'withdraw'),
          ),
          ListTile(
            leading: const Icon(Icons.account_balance_wallet_outlined),
            title: const Text('عرض كل المحافظ'),
            onTap: () => Navigator.pop(context, 'view'),
          ),
        ]),
      ),
    );
    if (action == 'view') {
      widget.onGoToWallets();
      return;
    }
    if (action == 'deposit' || action == 'withdraw') {
      if (!mounted) return;
      final result = await showModalBottomSheetWalletTx(
        context,
        repo,
        deposit: action == 'deposit',
      );
      if (!mounted) return;
      if (result == true) _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      color: pageBg,
      child: FutureBuilder<_HomeData>(
        future: _dataFuture,
        builder: (context, snapshot) {
          final data = snapshot.data;
          return RefreshIndicator(
            onRefresh: _load,
            child: ListView(
              padding: EdgeInsets.zero,
              children: [
                _Header(onOpenMenu: widget.onOpenMenu, onSearch: _openSearch),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
                  child: data == null
                      ? const Padding(
                          padding: EdgeInsets.symmetric(vertical: 60),
                          child: Center(child: CircularProgressIndicator()),
                        )
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Row(children: [
                              Expanded(
                                child: _MetricCard(
                                  title: 'صافي ربح اليوم',
                                  value: data.netProfitToday.toStringAsFixed(0),
                                  filled: false,
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: _MetricCard(
                                  title: 'مبيعات اليوم (${data.salesCountToday})',
                                  value: data.salesTotalToday.toStringAsFixed(0),
                                  filled: true,
                                ),
                              ),
                            ]),
                            const SizedBox(height: 10),
                            Row(children: [
                              Expanded(
                                child: _MetricCard(
                                  title: 'أرصدة المحافظ',
                                  value: data.walletBalance.toStringAsFixed(0),
                                  filled: false,
                                  onTap: widget.onGoToWallets,
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: _MetricCard(
                                  title: 'الخزنة (الدرج)',
                                  value: data.cashBalance.toStringAsFixed(0),
                                  filled: false,
                                  onTap: widget.onGoToWallets,
                                ),
                              ),
                            ]),
                            const SizedBox(height: 10),
                            Row(children: [
                              Expanded(
                                child: _MetricCard(
                                  title: 'على العملاء',
                                  value: data.customerDebt.toStringAsFixed(0),
                                  filled: false,
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: _MetricCard(
                                  title: 'في الصيانة',
                                  value: '${data.maintenanceOpenCount} جهاز',
                                  filled: false,
                                  isCount: true,
                                ),
                              ),
                            ]),
                            const SizedBox(height: 22),
                            const Text('عمليات سريعة',
                                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
                            const SizedBox(height: 10),
                            _NewSaleBanner(onTap: _openNewSale),
                            const SizedBox(height: 12),
                            GridView.count(
                              crossAxisCount: 2,
                              crossAxisSpacing: 10,
                              mainAxisSpacing: 10,
                              childAspectRatio: 1.55,
                              shrinkWrap: true,
                              physics: const NeverScrollableScrollPhysics(),
                              children: [
                                _QuickTile(
                                  icon: Icons.credit_card_rounded,
                                  label: 'إيداع / سحب محفظة',
                                  onTap: _openWalletChoice,
                                ),
                                _QuickTile(
                                  icon: Icons.build_rounded,
                                  label: 'استلام جهاز صيانة',
                                  onTap: _openNewMaintenanceTicket,
                                ),
                                _QuickTile(
                                  icon: Icons.phone_android_rounded,
                                  label: 'شراء موبايل مستعمل',
                                  onTap: _openBuyUsedPhone,
                                ),
                                _QuickTile(
                                  icon: Icons.local_shipping_rounded,
                                  label: 'شراء بضاعة',
                                  onTap: _openBuyGoods,
                                ),
                                _QuickTile(
                                  icon: Icons.lock_clock_rounded,
                                  label: 'تقفيل اليوم',
                                  onTap: () => _closeDay(data),
                                ),
                                _QuickTile(
                                  icon: Icons.payments_rounded,
                                  label: 'تسجيل مصروف',
                                  onTap: _openRecordExpense,
                                ),
                              ],
                            ),
                            const SizedBox(height: 22),
                            const Text('آخر عمليات اليوم',
                                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
                            const SizedBox(height: 10),
                            if (data.recentOps.isEmpty)
                              const Padding(
                                padding: EdgeInsets.symmetric(vertical: 16),
                                child: Text('لا توجد عمليات اليوم بعد', style: TextStyle(color: Colors.black54)),
                              )
                            else
                              ...data.recentOps.map((op) => _RecentOpTile(
                                    op: op,
                                    onTap: op.sale == null
                                        ? null
                                        : () async {
                                            final repo = _salesRepo ?? await getSalesRepository();
                                            if (!context.mounted) return;
                                            await Navigator.of(context).push(
                                              MaterialPageRoute(
                                                builder: (_) =>
                                                    SaleDetailScreen(repository: repo, sale: op.sale!),
                                              ),
                                            );
                                          },
                                  )),
                          ],
                        ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

/// Wraps the shared WalletTxSheet (from wallets_page.dart) as a bottom
/// sheet so the home quick-action reuses the exact same form/validation
/// logic as the Wallets tab instead of duplicating it.
Future<bool?> showModalBottomSheetWalletTx(BuildContext context, WalletRepository repository, {required bool deposit}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (_) => WalletTxSheet(repository: repository, deposit: deposit),
  );
}

class _Header extends StatelessWidget {
  const _Header({required this.onOpenMenu, required this.onSearch});
  final VoidCallback onOpenMenu;
  final VoidCallback onSearch;

  @override
  Widget build(BuildContext context) {
    final topPadding = MediaQuery.of(context).padding.top;
    final today = DateTime.now();
    final dateLabel = '${today.day}/${today.month}/${today.year}';
    return Container(
      width: double.infinity,
      padding: EdgeInsets.fromLTRB(16, topPadding + 10, 16, 16),
      color: navy,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Row(
              children: [
                IconButton(
                  onPressed: onOpenMenu,
                  icon: const Icon(Icons.menu_rounded, color: Colors.white),
                ),
                const SizedBox(width: 4),
                Flexible(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text(
                        'محل الأمانة موبايل',
                        style: TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w900),
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(dateLabel, style: const TextStyle(color: Colors.white70, fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          IconButton(onPressed: onSearch, icon: const Icon(Icons.search_rounded, color: Colors.white)),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.title,
    required this.value,
    required this.filled,
    this.isCount = false,
    this.onTap,
  });
  final String title;
  final String value;
  final bool filled;
  final bool isCount;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: filled ? navy : Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title,
                  style: TextStyle(
                    color: filled ? Colors.white70 : Colors.black54,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  )),
              const SizedBox(height: 8),
              Text(
                isCount ? value : value,
                style: TextStyle(
                  color: filled ? Colors.white : Colors.black87,
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NewSaleBanner extends StatelessWidget {
  const _NewSaleBanner({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: navy,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: const Padding(
          padding: EdgeInsets.symmetric(horizontal: 18, vertical: 18),
          child: Row(
            children: [
              SizedBox(
                width: 46,
                height: 46,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: Colors.white24,
                    borderRadius: BorderRadius.all(Radius.circular(14)),
                  ),
                  child: Icon(Icons.shopping_cart_rounded, color: Colors.white),
                ),
              ),
              SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('فانورة بيع جديدة',
                        style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w900)),
                    SizedBox(height: 4),
                    Text('موبايلات • إكسسوارات • قطع غيار • كروت',
                        style: TextStyle(color: Colors.white70, fontSize: 11)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _QuickTile extends StatelessWidget {
  const _QuickTile({required this.icon, required this.label, required this.onTap});
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(color: navy.withOpacity(0.08), borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, color: navy, size: 20),
              ),
              const SizedBox(height: 8),
              Text(
                label,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12.5),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RecentOpTile extends StatelessWidget {
  const _RecentOpTile({required this.op, this.onTap});
  final _RecentOp op;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final isIn = op.amount >= 0;
    final hh = op.at.hour.toString().padLeft(2, '0');
    final mm = op.at.minute.toString().padLeft(2, '0');
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        onTap: onTap,
        leading: CircleAvatar(
          backgroundColor: navy.withOpacity(0.08),
          child: Icon(op.icon, color: navy, size: 20),
        ),
        title: Text(op.title, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text('${op.subtitle} • $hh:$mm'),
        trailing: Text(
          '${isIn ? '+' : ''}${op.amount.toStringAsFixed(0)}',
          style: TextStyle(
            fontWeight: FontWeight.w900,
            color: isIn ? Colors.green.shade700 : Colors.red.shade700,
          ),
        ),
      ),
    );
  }
}
