import 'package:flutter/material.dart';
import 'features/inventory/inventory_page.dart';
import 'features/sales/sales_page.dart';
import 'features/sales/sales_provider.dart';
import 'features/customers/customers_page.dart';
import 'features/suppliers/suppliers_page.dart';
import 'features/installments/installments_page.dart';
import 'features/expenses/expenses_page.dart';
import 'features/maintenance/maintenance_page.dart';
import 'features/wallets/wallets_page.dart';
import 'features/reports/reports_page.dart';
import 'features/home/home_page.dart';
import 'features/settings/settings_page.dart';
import 'features/auth/auth_models.dart';
import 'features/auth/auth_service.dart';

void main() => runApp(const MobileShopApp());

class MobileShopApp extends StatelessWidget {
  const MobileShopApp({super.key});

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF0B1220);
    const gold = Color(0xFFD6A84F);
    final scheme = ColorScheme.fromSeed(seedColor: gold).copyWith(
      primary: navy,
      secondary: gold,
      surface: const Color(0xFFF7F8FA),
    );

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      locale: const Locale('ar'),
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: scheme,
        scaffoldBackgroundColor: const Color(0xFFF7F8FA),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFFF7F8FA),
          foregroundColor: navy,
          elevation: 0,
          surfaceTintColor: Colors.transparent,
        ),
        cardTheme: const CardTheme(
          elevation: 0,
          margin: EdgeInsets.zero,
          color: Colors.white,
          surfaceTintColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(18)),
            side: BorderSide(color: Color(0xFFE8EBF0)),
          ),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(14)),
            borderSide: BorderSide(color: Color(0xFFE1E5EA)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(14)),
            borderSide: BorderSide(color: Color(0xFFE1E5EA)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(14)),
            borderSide: BorderSide(color: gold, width: 1.6),
          ),
          contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 15),
        ),
        navigationDrawerTheme: const NavigationDrawerThemeData(
          backgroundColor: Colors.white,
          indicatorColor: Color(0xFFF3E8CC),
          tileHeight: 52,
        ),
      ),
      home: const _AppEntry(),
    );
  }
}

/// شاشة انتظار تحمّل الجلسة المحفوظة — تظهر للحظة عند فتح التطبيق.
class _AppEntry extends StatefulWidget {
  const _AppEntry();

  @override
  State<_AppEntry> createState() => _AppEntryState();
}

class _AppEntryState extends State<_AppEntry> {
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    await AuthService.instance.loadSession();
    if (mounted) setState(() => _ready = true);
  }

  @override
  Widget build(BuildContext context) {
    if (!_ready) {
      // شاشة Splash بسيطة أثناء تحميل الجلسة
      return const Directionality(
        textDirection: TextDirection.rtl,
        child: Scaffold(
          backgroundColor: Color(0xFF0B1220),
          body: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.phone_android_rounded,
                    color: Color(0xFFD6A84F), size: 64),
                SizedBox(height: 16),
                Text('Mobile Shop',
                    style: TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.w900)),
                SizedBox(height: 32),
                SizedBox(
                  width: 24,
                  height: 24,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: Color(0xFFD6A84F)),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return const DashboardShell();
  }
}

// ─────────────────────────────────────────────────────────────────────────────

class DashboardShell extends StatefulWidget {
  const DashboardShell({super.key});

  @override
  State<DashboardShell> createState() => _DashboardShellState();
}

class _DashboardShellState extends State<DashboardShell> {
  int index = 0;
  final _scaffoldKey = GlobalKey<ScaffoldState>();

  AccountSession? get _session => AuthService.instance.currentSession;
  bool get _isOnline => _session != null && _session!.token.isNotEmpty;

  static const drawerDestinations = [
    NavigationDrawerDestination(icon: Icon(Icons.dashboard_rounded), selectedIcon: Icon(Icons.dashboard_rounded, color: Color(0xFF0B1220)), label: Text('لوحة التحكم')),
    NavigationDrawerDestination(icon: Icon(Icons.point_of_sale_rounded), selectedIcon: Icon(Icons.point_of_sale_rounded, color: Color(0xFF0B1220)), label: Text('المبيعات')),
    NavigationDrawerDestination(icon: Icon(Icons.inventory_2_rounded), selectedIcon: Icon(Icons.inventory_2_rounded, color: Color(0xFF0B1220)), label: Text('المخزون')),
    NavigationDrawerDestination(icon: Icon(Icons.people_alt_rounded), selectedIcon: Icon(Icons.people_alt_rounded, color: Color(0xFF0B1220)), label: Text('العملاء')),
    NavigationDrawerDestination(icon: Icon(Icons.local_shipping_rounded), selectedIcon: Icon(Icons.local_shipping_rounded, color: Color(0xFF0B1220)), label: Text('الموردون')),
    NavigationDrawerDestination(icon: Icon(Icons.payments_rounded), selectedIcon: Icon(Icons.payments_rounded, color: Color(0xFF0B1220)), label: Text('الأقساط')),
    NavigationDrawerDestination(icon: Icon(Icons.build_rounded), selectedIcon: Icon(Icons.build_rounded, color: Color(0xFF0B1220)), label: Text('الصيانة')),
    NavigationDrawerDestination(icon: Icon(Icons.receipt_long_rounded), selectedIcon: Icon(Icons.receipt_long_rounded, color: Color(0xFF0B1220)), label: Text('المصروفات')),
    NavigationDrawerDestination(icon: Icon(Icons.analytics_rounded), selectedIcon: Icon(Icons.analytics_rounded, color: Color(0xFF0B1220)), label: Text('التقارير')),
    NavigationDrawerDestination(icon: Icon(Icons.store_rounded), selectedIcon: Icon(Icons.store_rounded, color: Color(0xFF0B1220)), label: Text('الفروع والمستخدمون')),
    NavigationDrawerDestination(icon: Icon(Icons.settings_rounded), selectedIcon: Icon(Icons.settings_rounded, color: Color(0xFF0B1220)), label: Text('الإعدادات')),
    NavigationDrawerDestination(icon: Icon(Icons.account_balance_wallet_rounded), selectedIcon: Icon(Icons.account_balance_wallet_rounded, color: Color(0xFF0B1220)), label: Text('المحافظ')),
  ];

  static const pages = [
    ('لوحة التحكم', Icons.dashboard_rounded),
    ('المبيعات', Icons.point_of_sale_rounded),
    ('المخزون', Icons.inventory_2_rounded),
    ('العملاء', Icons.people_alt_rounded),
    ('الموردون', Icons.local_shipping_rounded),
    ('الأقساط', Icons.payments_rounded),
    ('الصيانة', Icons.build_rounded),
    ('المصروفات', Icons.receipt_long_rounded),
    ('التقارير', Icons.analytics_rounded),
    ('الفروع والمستخدمون', Icons.store_rounded),
    ('الإعدادات', Icons.settings_rounded),
    ('المحافظ', Icons.account_balance_wallet_rounded),
  ];

  static const _walletsIndex = 11;

  void _goTo(int i) => setState(() => index = i);

  Future<void> _openNewSaleQuick() async {
    final repository = await getSalesRepository();
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => NewSaleScreen(repository: repository)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isHome = index == 0;
    final isOnline = _isOnline;

    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        key: _scaffoldKey,
        extendBodyBehindAppBar: isHome,
        appBar: isHome
            ? null
            : AppBar(
                title: Text(
                  pages[index].$1,
                  style: const TextStyle(
                      fontSize: 21, fontWeight: FontWeight.w800),
                ),
              ),
        drawer: NavigationDrawer(
          selectedIndex: index,
          onDestinationSelected: (value) {
            setState(() => index = value);
            Navigator.pop(context);
          },
          children: [
            const SizedBox(height: 22),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: const Color(0xFF0B1220),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(Icons.phone_android_rounded,
                        color: Color(0xFFD6A84F)),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Mobile Shop',
                            style: TextStyle(
                                fontSize: 18, fontWeight: FontWeight.w900)),
                        Text(
                          isOnline
                              ? _session!.displayName
                              : 'نظام إدارة المحل',
                          style: const TextStyle(
                              color: Colors.black54, fontSize: 12),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24),
              child: Text('الإدارة',
                  style: TextStyle(
                      fontSize: 12,
                      color: Colors.black45,
                      fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 6),
            ...drawerDestinations,
            const Padding(
              padding: EdgeInsets.fromLTRB(24, 18, 24, 8),
              child: Divider(),
            ),
            // ── مؤشر الوضع ─────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Row(children: [
                Icon(
                  isOnline ? Icons.cloud_done_rounded : Icons.cloud_off_rounded,
                  size: 14,
                  color: isOnline ? Colors.green.shade700 : Colors.black38,
                ),
                const SizedBox(width: 6),
                Text(
                  isOnline
                      ? '${_session!.branchName} • Online'
                      : 'Offline mode',
                  style: TextStyle(
                    fontSize: 12,
                    color:
                        isOnline ? Colors.green.shade700 : Colors.black45,
                  ),
                ),
              ]),
            ),
            const SizedBox(height: 8),
          ],
        ),
        body: _page(index),
        bottomNavigationBar: _BottomNavBar(
          currentIndex: index,
          onHome: () => _goTo(0),
          onSales: () => _goTo(1),
          onMaintenance: () => _goTo(6),
          onWallets: () => _goTo(_walletsIndex),
          onSell: _openNewSaleQuick,
        ),
      ),
    );
  }

  Widget _page(int i) {
    if (i == 0) {
      return HomePage(
        onOpenMenu: () => _scaffoldKey.currentState?.openDrawer(),
        onGoToWallets: () => _goTo(_walletsIndex),
      );
    }
    if (i == 1) return const SalesPage();
    if (i == 2) return const InventoryPage();
    if (i == 3) return const CustomersPage();
    if (i == 4) return const SuppliersPage();
    if (i == 5) return const InstallmentsPage();
    if (i == 6) return const MaintenancePage();
    if (i == 7) return const ExpensesPage();
    if (i == 8) return const ReportsPage();
    if (i == 10) {
      return SettingsPage(
        onSessionChanged: () => setState(() {}),
      );
    }
    if (i == _walletsIndex) return const WalletsPage();
    return GenericPage(title: pages[i].$1, icon: pages[i].$2);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// الـ widgets الثابتة (من main.dart الأصلي، بدون تغيير)
// ─────────────────────────────────────────────────────────────────────────────

class GenericPage extends StatelessWidget {
  const GenericPage({required this.title, required this.icon, super.key});
  final String title;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                  width: 82,
                  height: 82,
                  decoration: BoxDecoration(
                      color: const Color(0xFFF3E8CC),
                      borderRadius: BorderRadius.circular(24)),
                  child: Icon(icon,
                      size: 40, color: const Color(0xFF0B1220))),
              const SizedBox(height: 18),
              Text(title,
                  style: const TextStyle(
                      fontSize: 24, fontWeight: FontWeight.w900)),
              const SizedBox(height: 8),
              const Text('هذه الوحدة قيد التطوير.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.black54)),
            ],
          ),
        ),
      );
}

class _BottomNavBar extends StatelessWidget {
  const _BottomNavBar({
    required this.currentIndex,
    required this.onHome,
    required this.onSales,
    required this.onMaintenance,
    required this.onWallets,
    required this.onSell,
  });

  final int currentIndex;
  final VoidCallback onHome;
  final VoidCallback onSales;
  final VoidCallback onMaintenance;
  final VoidCallback onWallets;
  final VoidCallback onSell;

  static const _navy = Color(0xFF0B1220);
  static const _gold = Color(0xFFD6A84F);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: Color(0xFFE8EBF0))),
      ),
      child: SafeArea(
        child: SizedBox(
          height: 60,
          child: Row(
            children: [
              _NavItem(Icons.dashboard_rounded, 'الرئيسية', 0, currentIndex, onHome),
              _NavItem(Icons.point_of_sale_rounded, 'المبيعات', 1, currentIndex, onSales),
              // زرار البيع السريع في المنتصف
              Expanded(
                child: GestureDetector(
                  onTap: onSell,
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(
                        width: 46,
                        height: 46,
                        decoration: BoxDecoration(
                          color: _navy,
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: const Icon(Icons.add_rounded,
                            color: _gold, size: 26),
                      ),
                    ],
                  ),
                ),
              ),
              _NavItem(Icons.build_rounded, 'الصيانة', 6, currentIndex, onMaintenance),
              _NavItem(Icons.account_balance_wallet_rounded, 'المحافظ', 11, currentIndex, onWallets),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem(this.icon, this.label, this.itemIndex, this.currentIndex, this.onTap);

  final IconData icon;
  final String label;
  final int itemIndex;
  final int currentIndex;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final selected = itemIndex == currentIndex;
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon,
                color: selected ? const Color(0xFF0B1220) : Colors.black38,
                size: 24),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(
                    fontSize: 10,
                    color: selected ? const Color(0xFF0B1220) : Colors.black38,
                    fontWeight: selected
                        ? FontWeight.bold
                        : FontWeight.normal)),
          ],
        ),
      ),
    );
  }
}
