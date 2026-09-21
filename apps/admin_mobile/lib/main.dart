import 'package:flutter/material.dart';
import 'features/inventory/inventory_page.dart';
import 'features/sales/sales_page.dart';
import 'features/customers/customers_page.dart';
import 'features/suppliers/suppliers_page.dart';
import 'features/installments/installments_page.dart';
import 'features/expenses/expenses_page.dart';
import 'features/maintenance/maintenance_page.dart';

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
  ];

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
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
      ),
    );
  }

  Widget _page(int i) {
    if (i == 0) return const DashboardPage();
    if (i == 1) return const SalesPage();
    if (i == 2) return const InventoryPage();
    if (i == 3) return const CustomersPage();
    if (i == 4) return const SuppliersPage();
    if (i == 5) return const InstallmentsPage();
    if (i == 6) return const MaintenancePage();
    if (i == 7) return const ExpensesPage();
    if (i == 10) return const SettingsPage();
    return GenericPage(title: pages[i].$1, icon: pages[i].$2);
  }
}

class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: () async {},
    child: ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
      children: [
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF0B1220), Color(0xFF18253A)],
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
            ),
            borderRadius: BorderRadius.circular(24),
          ),
          child: const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('أهلاً بيك 👋', style: TextStyle(color: Colors.white70, fontSize: 14)),
              SizedBox(height: 5),
              Text('ملخص المحل اليوم', style: TextStyle(color: Colors.white, fontSize: 25, fontWeight: FontWeight.w900)),
              SizedBox(height: 8),
              Text('تابع المبيعات والمخزون والحركة اليومية من مكان واحد.', style: TextStyle(color: Colors.white60)),
            ],
          ),
        ),
        const SizedBox(height: 18),
        const Row(
          children: [
            Expanded(child: Metric(title: 'مبيعات اليوم', value: '12,450', suffix: 'ج.م', icon: Icons.trending_up_rounded)),
            SizedBox(width: 10),
            Expanded(child: Metric(title: 'صافي الربح', value: '3,120', suffix: 'ج.م', icon: Icons.account_balance_wallet_rounded)),
          ],
        ),
        const SizedBox(height: 10),
        const Row(
          children: [
            Expanded(child: Metric(title: 'الفواتير', value: '28', suffix: 'فاتورة', icon: Icons.receipt_long_rounded)),
            SizedBox(width: 10),
            Expanded(child: Metric(title: 'مخزون منخفض', value: '7', suffix: 'أصناف', icon: Icons.warning_amber_rounded)),
          ],
        ),
        const SizedBox(height: 22),
        const Text('إجراءات سريعة', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
        const SizedBox(height: 10),
        GridView.count(
          crossAxisCount: 2,
          crossAxisSpacing: 10,
          mainAxisSpacing: 10,
          childAspectRatio: 2.7,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          children: const [
            QuickAction(icon: Icons.point_of_sale_rounded, title: 'فاتورة بيع'),
            QuickAction(icon: Icons.add_box_rounded, title: 'إضافة منتج'),
            QuickAction(icon: Icons.payments_rounded, title: 'تحصيل قسط'),
            QuickAction(icon: Icons.receipt_long_rounded, title: 'مصروف جديد'),
          ],
        ),
        const SizedBox(height: 22),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('تنبيهات مهمة', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
            TextButton(onPressed: () {}, child: const Text('عرض الكل')),
          ],
        ),
        const AlertTile(icon: Icons.inventory_2_outlined, title: '7 أصناف وصلت لحد إعادة الطلب', subtitle: 'راجع المخزون قبل نفاد الكمية.'),
        const SizedBox(height: 8),
        const AlertTile(icon: Icons.cloud_off_rounded, title: 'المزامنة متوقفة', subtitle: 'العمليات ستُحفظ محلياً لحين الاتصال.'),
      ],
    ),
  );
}

class Metric extends StatelessWidget {
  const Metric({required this.title, required this.value, required this.suffix, required this.icon, super.key});
  final String title;
  final String value;
  final String suffix;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: const Color(0xFFF3E8CC),
              borderRadius: BorderRadius.circular(13),
            ),
            child: Icon(icon, color: const Color(0xFF0B1220), size: 21),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(color: Colors.black54, fontSize: 11)),
                const SizedBox(height: 2),
                Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
                Text(suffix, style: const TextStyle(color: Colors.black45, fontSize: 10)),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class QuickAction extends StatelessWidget {
  const QuickAction({required this.icon, required this.title, super.key});
  final IconData icon;
  final String title;

  @override
  Widget build(BuildContext context) => Card(
    child: InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: () {},
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Row(
          children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(
                color: const Color(0xFFF3E8CC),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: const Color(0xFF0B1220), size: 20),
            ),
            const SizedBox(width: 9),
            Expanded(child: Text(title, style: const TextStyle(fontWeight: FontWeight.w800))),
          ],
        ),
      ),
    ),
  );
}

class AlertTile extends StatelessWidget {
  const AlertTile({required this.icon, required this.title, required this.subtitle, super.key});
  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
      leading: Container(
        width: 42,
        height: 42,
        decoration: BoxDecoration(
          color: const Color(0xFFF3E8CC),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(icon, color: const Color(0xFF0B1220)),
      ),
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
      subtitle: Text(subtitle),
      trailing: const Icon(Icons.chevron_left_rounded),
    ),
  );
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
