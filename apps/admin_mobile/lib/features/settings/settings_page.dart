import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';

import 'about_page.dart';
import 'backup_service.dart';
import '../auth/auth_models.dart';
import '../auth/auth_service.dart';
import '../auth/login_page.dart';
import '../inventory/local_store.dart';
import '../sync/sync_runner.dart';
import '../sync/sync_time_format.dart';
import '../sync/sync_dashboard_page.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key, this.onSessionChanged});

  /// بيتنادى لما يتسجل دخول أو يتسجل خروج — عشان الـ Shell يحدّث الـ AppBar.
  final void Function()? onSessionChanged;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  bool _busy = false;
  AccountSession? _session;
  int _pendingCount = 0;
  int _conflictCount = 0;
  DateTime? _lastSyncAt;
  bool _syncing = false;
  List<({String commandId, String command, String status, String? error})> _syncFailures = const [];

  @override
  void initState() {
    super.initState();
    _session = AuthService.instance.currentSession;
    _refreshSyncStatus();
  }

  Future<void> _refreshSyncStatus() async {
    final store = await LocalStore.open();
    final count = await store.pendingCommandCount();
    final conflicts = await store.conflictCount();
    final lastSync = await store.getLastSyncAt();
    final failures = await store.terminalFailures();
    if (!mounted) return;
    setState(() {
      _pendingCount = count;
      _conflictCount = conflicts;
      _lastSyncAt = lastSync;
      _syncFailures = failures;
    });
  }

  // ─── Auth ─────────────────────────────────────────────────────────────────

  void _openLogin() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => LoginPage(
          onLoggedIn: (session) {
            Navigator.pop(context);
            setState(() => _session = session);
            widget.onSessionChanged?.call();
            // 5.1: catch up whatever's been queuing in the outbox — this
            // could be the very first login on a device with pre-existing
            // offline data, or a branch switch. Fire-and-forget, same
            // reasoning as main.dart's app-start drain.
            _syncNow(showBusyIndicator: false);
          },
        ),
      ),
    );
  }

  Future<void> _logout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => Directionality(
        textDirection: TextDirection.rtl,
        child: AlertDialog(
          title: const Text('تسجيل الخروج'),
          content: const Text(
            'ستظل بياناتك المحلية كما هي على هذا الجهاز، '
            'لكن لن يحدث أي مزامنة حتى تسجل الدخول مجددًا.',
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('إلغاء')),
            FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('تسجيل الخروج')),
          ],
        ),
      ),
    );
    if (confirmed != true || !mounted) return;
    await AuthService.instance.logout();
    // مسح الـ cursor ووقت آخر مزامنة عشان لو دخل حساب تاني يبدأ من الأول
    final store = await LocalStore.open();
    await store.resetSyncCursor();
    await store.resetLastSyncAt();
    setState(() => _session = null);
    widget.onSessionChanged?.call();
  }

  // ─── Sync (5.1 + 5.2) ────────────────────────────────────────────────────

  Future<void> _syncNow({bool showBusyIndicator = true}) async {
    if (_syncing) return;
    setState(() {
      _syncing = true;
      if (showBusyIndicator) _busy = true;
    });
    try {
      final store = await LocalStore.open();

      // 5.1 + 5.2 عبر SyncRunner: يرفع أوامر الـ outbox المحلية للسيرفر
      // الأول، وبعدين يجيب التغييرات الجديدة، وبيسجّل "آخر مزامنة" لو
      // فعليًا اتكلمنا مع السيرفر (راجع SyncRunner.run لتفاصيل الشرط).
      final result = await SyncRunner(store).run();
      if (!mounted) return;

      await _refreshSyncStatus();
      if (!mounted) return;

      // بناء رسالة الحالة
      if (result.hasTransportError) {
        _showSnack('تعذّرت المزامنة: ${result.transportError}', isError: true);
      } else if (result.upload.terminalFailures > 0) {
        _showSnack(
          'تمت المزامنة مع ${result.upload.terminalFailures} عملية مرفوضة — التفاصيل تحت.',
          isError: true,
        );
      } else if (result.upload.applied > 0 || result.download.applied > 0) {
        final parts = <String>[];
        if (result.upload.applied > 0) parts.add('رُفع ${result.upload.applied} عملية');
        if (result.download.applied > 0) parts.add('نُزّل ${result.download.applied} تغيير');
        _showSnack('تمت المزامنة — ${parts.join(' ، ')}.');
      } else {
        _showSnack('البيانات محدّثة، لا يوجد تغييرات.');
      }
    } finally {
      if (mounted) {
        setState(() {
          _syncing = false;
          if (showBusyIndicator) _busy = false;
        });
      }
    }
  }

  // ─── Sync Dashboard (5.3) ────────────────────────────────────────────────

  Future<void> _openSyncDashboard() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const SyncDashboardPage()),
    );
    // ممكن يكون المستخدم عمل "مزامنة الآن" جوا الشاشة — حدّث الملخّص هنا.
    _refreshSyncStatus();
  }

  // ─── Backup ───────────────────────────────────────────────────────────────

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
      builder: (ctx) => Directionality(
        textDirection: TextDirection.rtl,
        child: AlertDialog(
          title: const Text('استيراد نسخة احتياطية'),
          content: const Text(
            'سيتم استبدال كل البيانات الحالية على هذا الجهاز ببيانات الملف المختار. '
            'هذا الإجراء لا يمكن التراجع عنه. هل تريد المتابعة؟',
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('إلغاء')),
            FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('استبدال البيانات')),
          ],
        ),
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
        builder: (ctx) => Directionality(
          textDirection: TextDirection.rtl,
          child: AlertDialog(
            title: const Text('تم الاستيراد بنجاح'),
            content: Text(
              'تم استعادة ${importResult.recordCount} سجل من نسخة بتاريخ '
              '${importResult.exportedAt.toLocal().toString().split('.').first}.\n\n'
              'أعد فتح التطبيق الآن لتحميل البيانات المستعادة في كل الشاشات.',
            ),
            actions: [
              FilledButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('حسنًا'))
            ],
          ),
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
      SnackBar(
          content: Text(message),
          backgroundColor: isError ? Colors.red.shade700 : null),
    );
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final isOnline = _session != null && _session!.token.isNotEmpty;

    return Stack(
      children: [
        ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
          children: [
            const Text('إعدادات النظام',
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
            const SizedBox(height: 6),
            const Text('الحساب السحابي، النسخ الاحتياطي، ومعلومات التطبيق.',
                style: TextStyle(color: Colors.black54)),
            const SizedBox(height: 18),

            // ── الحساب السحابي ─────────────────────────────────────────────
            const _SectionLabel('الحساب السحابي'),
            Card(
              child: Column(
                children: [
                  // مؤشر الحالة
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: isOnline
                          ? const Color(0xFFE8F5E9)
                          : const Color(0xFFF5F5F5),
                      borderRadius: const BorderRadius.vertical(
                          top: Radius.circular(18)),
                    ),
                    child: Row(children: [
                      Icon(
                        isOnline
                            ? Icons.cloud_done_rounded
                            : Icons.cloud_off_rounded,
                        color: isOnline
                            ? Colors.green.shade700
                            : Colors.black45,
                        size: 20,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              isOnline ? 'متصل بالسيرفر' : 'غير متصل (Offline)',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: isOnline
                                    ? Colors.green.shade800
                                    : Colors.black87,
                              ),
                            ),
                            if (isOnline) ...[
                              const SizedBox(height: 2),
                              Text(
                                '${_session!.displayName} • ${_session!.branchName}',
                                style: const TextStyle(
                                    fontSize: 12, color: Colors.black54),
                              ),
                              Text(
                                _session!.email,
                                style: const TextStyle(
                                    fontSize: 11, color: Colors.black38),
                              ),
                            ] else
                              const Text(
                                'البيانات تُحفظ محليًا على هذا الجهاز فقط',
                                style: TextStyle(
                                    fontSize: 12, color: Colors.black45),
                              ),
                          ],
                        ),
                      ),
                    ]),
                  ),
                  const Divider(height: 1),
                  if (!isOnline)
                    ListTile(
                      leading: const Icon(Icons.login_rounded),
                      title: const Text('تسجيل الدخول',
                          style: TextStyle(fontWeight: FontWeight.bold)),
                      subtitle: const Text(
                          'ربط بالسيرفر لمزامنة البيانات مع الفروع'),
                      trailing: const Icon(Icons.chevron_left),
                      onTap: _openLogin,
                    )
                  else ...[
                    ListTile(
                      leading: const Icon(Icons.swap_horiz_rounded),
                      title: const Text('تغيير الفرع'),
                      subtitle: Text(_session!.branchName),
                      trailing: const Icon(Icons.chevron_left),
                      onTap: _openLogin,
                    ),
                    const Divider(height: 1),
                    ListTile(
                      leading: _syncing
                          ? const SizedBox(
                              width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.sync_rounded),
                      title: const Text('مزامنة الآن'),
                      subtitle: Text(
                        _pendingCount > 0
                            ? '$_pendingCount عملية بانتظار الرفع للسيرفر'
                            : 'كل البيانات متزامنة مع السيرفر',
                      ),
                      trailing: _syncing ? null : const Icon(Icons.chevron_left),
                      onTap: _syncing ? null : () => _syncNow(),
                    ),
                    const Divider(height: 1),
                    ListTile(
                      leading: const Icon(Icons.dashboard_customize_outlined),
                      title: const Text('لوحة تفاصيل المزامنة'),
                      subtitle: Text(
                        'آخر مزامنة: ${formatSyncTime(_lastSyncAt)}'
                        '${_conflictCount > 0 ? ' • $_conflictCount تعارض' : ''}',
                      ),
                      trailing: const Icon(Icons.chevron_left),
                      onTap: _openSyncDashboard,
                    ),
                    if (_syncFailures.isNotEmpty) ...[
                      const Divider(height: 1),
                      ListTile(
                        leading: const Icon(Icons.error_outline_rounded, color: Colors.red),
                        title: Text('${_syncFailures.length} عملية مرفوضة من السيرفر',
                            style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
                        subtitle: Text(
                          _syncFailures.first.error ?? _syncFailures.first.status,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        trailing: const Icon(Icons.chevron_left),
                        isThreeLine: true,
                        onTap: _openSyncDashboard,
                      ),
                    ],
                    const Divider(height: 1),
                    ListTile(
                      leading: const Icon(Icons.logout_rounded,
                          color: Colors.red),
                      title: const Text('تسجيل الخروج',
                          style: TextStyle(color: Colors.red)),
                      onTap: _logout,
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 18),

            // ── النسخ الاحتياطي ────────────────────────────────────────────
            const _SectionLabel('النسخ الاحتياطي'),
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.upload_outlined),
                    title: const Text('تصدير نسخة احتياطية'),
                    subtitle: const Text(
                        'حفظ كل البيانات الحالية في ملف يمكن مشاركته أو حفظه'),
                    trailing: const Icon(Icons.chevron_left),
                    onTap: _busy ? null : _exportBackup,
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.download_outlined),
                    title: const Text('استيراد نسخة احتياطية'),
                    subtitle: const Text(
                        'استعادة البيانات من ملف نسخة احتياطية سابق'),
                    trailing: const Icon(Icons.chevron_left),
                    onTap: _busy ? null : _importBackup,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),

            // ── عن التطبيق ─────────────────────────────────────────────────
            const _SectionLabel('عن التطبيق'),
            Card(
              child: ListTile(
                leading: const Icon(Icons.info_outline),
                title: const Text('عن التطبيق'),
                subtitle: const Text(
                    'الإصدار، طريقة تخزين البيانات، ووضع الاتصال'),
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
            color: Colors.black.withOpacity(0.06),
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
        child: Text(text,
            style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: Colors.black54)),
      );
}
