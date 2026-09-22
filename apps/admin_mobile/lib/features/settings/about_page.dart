import 'package:flutter/material.dart';

/// Keep in sync with the `version:` line in pubspec.yaml — there's no
/// package_info_plus dependency yet, so this is the single manual source
/// of truth for the version shown to the user.
const String appVersion = '1.0.0';
const String appBuildNumber = '1';

class AboutPage extends StatelessWidget {
  const AboutPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('عن التطبيق')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 28),
        children: [
          Center(
            child: Container(
              width: 84,
              height: 84,
              decoration: BoxDecoration(
                color: const Color(0xFF0B1220),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Icon(Icons.phone_android_rounded, color: Color(0xFFD6A84F), size: 40),
            ),
          ),
          const SizedBox(height: 16),
          const Center(
            child: Text('Mobile Shop', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
          ),
          const SizedBox(height: 4),
          const Center(
            child: Text(
              'الإصدار $appVersion (build $appBuildNumber)',
              style: TextStyle(color: Colors.black54),
            ),
          ),
          const SizedBox(height: 24),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'نظام إدارة محل موبايلات: مبيعات، مخزون، عملاء، موردون، أقساط، '
                'صيانة، ومصروفات — يعمل بالكامل بدون إنترنت (Offline-first)، '
                'مع الاستعداد لمزامنة مستقبلية مع حساب سحابي مركزي.',
                style: TextStyle(height: 1.6),
              ),
            ),
          ),
          const SizedBox(height: 10),
          const Card(
            child: Column(
              children: [
                ListTile(
                  leading: Icon(Icons.storage_outlined),
                  title: Text('تخزين البيانات'),
                  subtitle: Text('قاعدة بيانات محلية على الجهاز (SQLite) — لا يتم رفع أي بيانات تلقائيًا.'),
                ),
                Divider(height: 1),
                ListTile(
                  leading: Icon(Icons.cloud_off_outlined),
                  title: Text('وضع الاتصال'),
                  subtitle: Text('غير متصل بالكامل حاليًا. ربط الحساب السحابي قيد التطوير.'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
