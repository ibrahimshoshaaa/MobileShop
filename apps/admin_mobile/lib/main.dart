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
import 'features/home/home_page.dart';

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
      home: const DashboardShell(),
    );
  }
}

class DashboardShell extends StatefulWidget {
  const DashboardShell({super.key});

  @override
  State<DashboardShell> createState() => _DashboardShellState();
}

class _DashboardShellState extends State<DashboardShell> {
  int index = 0;
  final _scaffoldKey = GlobalKey<ScaffoldState>();

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
                  style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
                ),
                actions: [
                  IconButton(onPressed: () {}, icon: const Icon(Icons.sync_rounded)),
                  IconButton(onPressed: () {}, icon: const Icon(Icons.notifications_none_rounded)),
                  const SizedBox(width: 8),
                ],
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
                    child: const Icon(Icons.phone_android_rounded, color: Color(0xFFD6A84F)),
                  ),
                  const SizedBox(width: 12),
                  const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Mobile Shop', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
                      Text('نظام إدارة المحل', style: TextStyle(color: Colors.black54, fontSize: 12)),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24),
              child: Text('الإدارة', style: TextStyle(fontSize: 12, color: Colors.black45, fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 6),
            ...drawerDestinations,
            const Padding(
              padding: EdgeInsets.fromLTRB(24, 18, 24, 8),
              child: Divider(),
            ),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24),
              child: Text('●  Offline mode', style: TextStyle(fontSize: 12, color: Colors.black45)),
            ),
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
    if (i == 10) return const SettingsPage();
    if (i == _walletsIndex) return const WalletsPage();
    return GenericPage(title: pages[i].$1, icon: pages[i].$2);
  }
}

/// Custom bottom bar matching the requested design: المحافظ / الصيانة /
/// بيع (raised center action, pushes straight to a new sale) / المبيعات /
/// الرئيسية, laid out right-to-left under the app's RTL directionality.
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

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        height: 66,
        decoration: const BoxDecoration(
          color: Colors.white,
          boxShadow: [BoxShadow(color: Color(0x14000000), blurRadius: 12, offset: Offset(0, -2))],
        ),
        child: Row(
          children: [
            _NavItem(icon: Icons.home_rounded, label: 'الرئيسية', selected: currentIndex == 0, onTap: onHome),
            _NavItem(icon: Icons.receipt_long_rounded, label: 'المبيعات', selected: currentIndex == 1, onTap: onSales),
            _SellButton(onTap: onSell),
            _NavItem(icon: Icons.build_rounded, label: 'الصيانة', selected: currentIndex == 6, onTap: onMaintenance),
            _NavItem(icon: Icons.account_balance_wallet_rounded, label: 'المحافظ', selected: currentIndex == 11, onTap: onWallets),
          ],
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({required this.icon, required this.label, required this.selected, required this.onTap});
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? const Color(0xFF0F3E5C) : Colors.black45;
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 3),
            Text(label, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    );
  }
}

class _SellButton extends StatelessWidget {
  const _SellButton({required this.onTap});
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          InkWell(
            onTap: onTap,
            customBorder: const CircleBorder(),
            child: Container(
              width: 48,
              height: 48,
              decoration: const BoxDecoration(color: Color(0xFF0F3E5C), shape: BoxShape.circle),
              child: const Icon(Icons.shopping_cart_rounded, color: Colors.white, size: 22),
            ),
          ),
          const SizedBox(height: 3),
          const Text('بيع', style: TextStyle(color: Color(0xFF0F3E5C), fontSize: 11, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}


class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
    children: [
      const Text('إعدادات النظام', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
      const SizedBox(height: 6),
      const Text('تحكم في الحساب والمزامنة والأمان.', style: TextStyle(color: Colors.black54)),
      const SizedBox(height: 18),
      Card(child: SwitchListTile(
        value: false,
        onChanged: (_) {},
        title: const Text('Online', style: TextStyle(fontWeight: FontWeight.bold)),
        subtitle: const Text('ربط الحساب بالسيرفر المركزي'),
        secondary: const Icon(Icons.cloud_outlined),
      )),
      const SizedBox(height: 10),
      const Card(child: Column(children: [
        ListTile(leading: Icon(Icons.account_circle_outlined), title: Text('حساب الشركة'), subtitle: Text('تسجيل الدخول وربط الفروع'), trailing: Icon(Icons.chevron_left)),
        Divider(height: 1),
        ListTile(leading: Icon(Icons.backup_outlined), title: Text('النسخ الاحتياطي'), subtitle: Text('إعدادات النسخ والاسترجاع'), trailing: Icon(Icons.chevron_left)),
        Divider(height: 1),
        ListTile(leading: Icon(Icons.security_outlined), title: Text('الأمان والصلاحيات'), subtitle: Text('المستخدمون والأدوار وسجل التدقيق'), trailing: Icon(Icons.chevron_left)),
      ])),
    ],
  );
}

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
              borderRadius: BorderRadius.circular(24),
            ),
            child: Icon(icon, size: 40, color: const Color(0xFF0B1220)),
          ),
          const SizedBox(height: 18),
          Text(title, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          const Text('هذه الوحدة جاهزة للربط بطبقة البيانات والأوامر الخلفية.', textAlign: TextAlign.center, style: TextStyle(color: Colors.black54)),
          const SizedBox(height: 20),
          FilledButton.icon(onPressed: () {}, icon: const Icon(Icons.add), label: const Text('إضافة جديد')),
        ],
      ),
    ),
  );
}
