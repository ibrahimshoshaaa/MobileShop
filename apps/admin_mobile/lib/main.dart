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
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    locale: const Locale('ar'),
    theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
    home: const DashboardShell(),
  );
}

class DashboardShell extends StatefulWidget {
  const DashboardShell({super.key});
  @override State<DashboardShell> createState() => _DashboardShellState();
}

class _DashboardShellState extends State<DashboardShell> {
  int index = 0;
  final pages = const [
    ('لوحة التحكم', Icons.dashboard), ('المبيعات', Icons.point_of_sale),
    ('المخزون', Icons.inventory_2), ('العملاء', Icons.people),
    ('الموردون', Icons.local_shipping), ('الأقساط', Icons.payments),
    ('الصيانة', Icons.build), ('المصروفات', Icons.receipt_long),
    ('التقارير', Icons.analytics), ('الفروع والمستخدمون', Icons.store),
    ('الإعدادات', Icons.settings),
  ];
  @override
  Widget build(BuildContext context) => Directionality(
    textDirection: TextDirection.rtl,
    child: Scaffold(
      appBar: AppBar(title: Text('Mobile Shop ERP • ${pages[index].$1}'), actions: [
        IconButton(onPressed: () {}, icon: const Icon(Icons.sync)),
        IconButton(onPressed: () {}, icon: const Icon(Icons.notifications_none)),
      ]),
      drawer: Drawer(child: ListView(children: [
        const DrawerHeader(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(Icons.store, size: 42), SizedBox(height: 8), Text('إدارة المحل', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)), Text('وضع Offline / Online')])),
        for (var i = 0; i < pages.length; i++) ListTile(selected: index == i, leading: Icon(pages[i].$2), title: Text(pages[i].$1), onTap: () { setState(() => index = i); Navigator.pop(context); }),
      ])),
      body: _page(index),
    ),
  );

  Widget _page(int i) {
    if (i == 0) return const DashboardPage();
    if (i == 1) return const SalesPage();
    if (i == 2) return const InventoryPage();
    if (i == 3) return const CustomersPage();
    if (i == 4) return const SuppliersPage();
    if (i == 5) return const InstallmentsPage();
    if (i == 7) return const ExpensesPage();
    if (i == 6) return const MaintenancePage();
    if (i == 10) return const SettingsPage();
    return GenericPage(title: pages[i].$1, icon: pages[i].$2);
  }
}

class DashboardPage extends StatelessWidget { const DashboardPage({super.key});
  @override Widget build(BuildContext c) => ListView(padding: const EdgeInsets.all(16), children: [
    Wrap(spacing: 12, runSpacing: 12, children: const [Metric('مبيعات اليوم', '12,450 ج.م', Icons.trending_up), Metric('صافي الربح', '3,120 ج.م', Icons.account_balance_wallet), Metric('فواتير اليوم', '28', Icons.receipt), Metric('منتجات منخفضة', '7', Icons.warning_amber)]),
    const SizedBox(height: 20), const Text('اختصارات سريعة', style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold)),
    Wrap(spacing: 8, children: ['فاتورة بيع', 'إضافة منتج', 'تحصيل قسط', 'مصروف جديد', 'تقفيل اليوم'].map((x) => ActionChip(label: Text(x), onPressed: () {})).toList()),
    const SizedBox(height: 20), const Card(child: ListTile(leading: Icon(Icons.cloud_done), title: Text('حالة المزامنة'), subtitle: Text('الوضع الحالي: Offline • 0 عمليات معلقة'))),
  ]);
}
class Metric extends StatelessWidget { final String title, value; final IconData icon; const Metric(this.title,this.value,this.icon,{super.key}); @override Widget build(BuildContext c)=>SizedBox(width: 160, child: Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[Icon(icon), const SizedBox(height:8), Text(title), Text(value, style: const TextStyle(fontSize:18,fontWeight:FontWeight.bold))])))); }
class SettingsPage extends StatelessWidget { const SettingsPage({super.key}); @override Widget build(BuildContext c)=>ListView(padding:const EdgeInsets.all(16),children:[SwitchListTile(value:false,onChanged:(_){},title:const Text('تفعيل Online'),subtitle:const Text('ربط الحساب بالسيرفر المركزي')),const ListTile(leading:Icon(Icons.account_circle),title:Text('حساب الشركة'),subtitle:Text('تسجيل الدخول وربط الفروع')),const ListTile(leading:Icon(Icons.backup),title:Text('النسخ الاحتياطي'),subtitle:Text('إعدادات النسخ والاسترجاع')),const ListTile(leading:Icon(Icons.security),title:Text('الأمان والصلاحيات'),subtitle:Text('المستخدمون والأدوار وسجل التدقيق'))]); }
class GenericPage extends StatelessWidget { final String title; final IconData icon; const GenericPage({required this.title,required this.icon,super.key}); @override Widget build(BuildContext c)=>Center(child:Column(mainAxisAlignment:MainAxisAlignment.center,children:[Icon(icon,size:72),const SizedBox(height:12),Text(title,style:const TextStyle(fontSize:25,fontWeight:FontWeight.bold)),const SizedBox(height:8),const Text('الشاشة الأساسية جاهزة للربط بطبقة Commands الخلفية'),const SizedBox(height:20),ElevatedButton(onPressed:(){},child:const Text('إضافة جديد'))])); }
