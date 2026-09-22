import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';

import 'about_page.dart';
import 'backup_service.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  bool _busy = false;

  Future<void> _exportBackup() async {
    setState(() => _busy = true);
    try {
      final service = await getBackupService();
      final file = await service.exportToFile();
      if (!mounted) return;
      await SharePlus.instance.share(
        ShareParams(
          files: [XFile(file.path, mimeType: 'application/json')],
          subject: 'نسخة احتياطية - Mobile Shop',
          text: 'نسخة احتياطية من بيانات Mobile Shop.',
        ),
      );
      if (!mounted) return;
      _showSnack('تم إنشاء النسخة الاحتياطية: ${file.uri.pathSegments.last}');
    } catch (e) {
      if (!mounted) return;
      _showSnack('تعذّر إنشاء النسخة الاحتياطية: $e', isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _importBackup() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['json'],
      withData: false,
    );
    if (result == null || result.files.single.path == null) return;
    final path = result.files.single.path!;

    if (!mounted) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('استيراد نسخة احتياطية'),
        content: const Text(
          'سيتم استبدال كل البيانات الحالية على هذا الجهاز ببيانات الملف المختار. '
          'هذا الإجراء لا يمكن التراجع عنه. هل تريد المتابعة؟',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('إلغاء')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('استبدال البيانات')),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _busy = true);
    try {
      final service = await getBackupService();
      final importResult = await service.importFromFile(File(path));
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('تم الاستيراد بنجاح'),
          content: Text(
            'تم استعادة ${importResult.recordCount} سجل من نسخة بتاريخ '
            '${importResult.exportedAt.toLocal().toString().split('.').first}.\n\n'
            'أعد فتح التطبيق الآن لتحميل البيانات المستعادة في كل الشاشات.',
          ),
          actions: [FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('حسنًا'))],
        ),
      );
    } on FormatException catch (e) {
      if (!mounted) return;
      _showSnack(e.message, isError: true);
    } catch (e) {
      if (!mounted) return;
      _showSnack('تعذّر استيراد النسخة الاحتياطية: $e', isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _showSnack(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: isError ? Colors.red.shade700 : null),
    );
  }

  void _showCloudAccountInfo() {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('الحساب السحابي'),
        content: const Text(
          'ربط الحساب السحابي (تسجيل الدخول ومزامنة الفروع مع السيرفر المركزي) '
          'قيد التطوير حاليًا ولم يتم تفعيله بعد. التطبيق يعمل بالكامل محليًا على '
          'هذا الجهاز إلى أن يتم إطلاق هذه الميزة.',
        ),
        actions: [FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('حسنًا'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
          children: [
            const Text('إعدادات النظام', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
            const SizedBox(height: 6),
            const Text('النسخ الاحتياطي، الحساب السحابي، ومعلومات التطبيق.', style: TextStyle(color: Colors.black54)),
            const SizedBox(height: 18),

            const _SectionLabel('الحساب السحابي'),
            Card(
              child: ListTile(
                leading: const Icon(Icons.cloud_off_outlined),
                title: const Text('غير متصل', style: TextStyle(fontWeight: FontWeight.bold)),
                subtitle: const Text('التطبيق يعمل محليًا فقط — ربط الحساب السحابي قيد التطوير'),
                trailing: const _SoonBadge(),
                onTap: _showCloudAccountInfo,
              ),
            ),
            const SizedBox(height: 18),

            const _SectionLabel('النسخ الاحتياطي'),
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.upload_outlined),
                    title: const Text('تصدير نسخة احتياطية'),
                    subtitle: const Text('حفظ كل البيانات الحالية في ملف يمكن مشاركته أو حفظه'),
                    trailing: const Icon(Icons.chevron_left),
                    onTap: _busy ? null : _exportBackup,
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.download_outlined),
                    title: const Text('استيراد نسخة احتياطية'),
                    subtitle: const Text('استعادة البيانات من ملف نسخة احتياطية سابق'),
                    trailing: const Icon(Icons.chevron_left),
                    onTap: _busy ? null : _importBackup,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),

            const _SectionLabel('عن التطبيق'),
            Card(
              child: ListTile(
                leading: const Icon(Icons.info_outline),
                title: const Text('عن التطبيق'),
                subtitle: const Text('الإصدار، طريقة تخزين البيانات، ووضع الاتصال'),
                trailing: const Icon(Icons.chevron_left),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const AboutPage()),
                ),
              ),
            ),
          ],
        ),
        if (_busy)
          Container(
            color: Colors.black.withValues(alpha: 0.06),
            child: const Center(child: CircularProgressIndicator()),
          ),
      ],
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 0, 4, 8),
        child: Text(text, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.black54)),
      );
}

class _SoonBadge extends StatelessWidget {
  const _SoonBadge();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: const Color(0xFFF3E8CC),
          borderRadius: BorderRadius.circular(999),
        ),
        child: const Text('قريبًا', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Color(0xFF0B1220))),
      );
}
