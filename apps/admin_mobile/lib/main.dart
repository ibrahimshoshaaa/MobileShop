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
      trailing: Icon(Icons.chevron_left_rounded),
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
        ListTile(leading: const Icon(Icons.account_circle_outlined), title: const Text('حساب الشركة'), subtitle: const Text('تسجيل الدخول وربط الفروع'), trailing: const Icon(Icons.chevron_left)),
        Divider(height: 1),
        ListTile(leading: Icon(Icons.backup_outlined), title: Text('النسخ الاحتياطي'), subtitle: Text('إعدادات النسخ والاسترجاع'), trailing: Icon(Icons.chevron_left)),
        const Divider(height: 1),
        ListTile(leading: const Icon(Icons.security_outlined), title: const Text('الأمان والصلاحيات'), subtitle: const Text('المستخدمون والأدوار وسجل التدقيق'), trailing: const Icon(Icons.chevron_left)),
      ])),
    ],
  );
}

class GenericPage extends StatelessWidget {