import 'package:flutter/material.dart';

import '../inventory/local_store.dart';
import 'sync_runner.dart';
import 'sync_time_format.dart';

/// 5.3 — Sync Dashboard: a dedicated screen (not just the short summary in
/// Settings) showing Pending Commands, Last Sync, Sync Errors, and a
/// Conflict Count, plus a manual "مزامنة الآن" — reusing exactly the same
/// [SyncRunner] Settings' quick action and the app-start drain use, so all
/// three ways of triggering a sync behave identically and share the same
/// "آخر مزامنة" timestamp.
///
/// Reachable from Settings' Cloud Account section
/// ("لوحة تفاصيل المزامنة"), which still keeps its own short summary +
/// quick sync button — this page is the fuller view for when the person
/// wants to actually see what's pending/rejected, not a replacement for
/// the quick action.
class SyncDashboardPage extends StatefulWidget {
  const SyncDashboardPage({super.key});

  @override
  State<SyncDashboardPage> createState() => _SyncDashboardPageState();
}

class _SyncDashboardPageState extends State<SyncDashboardPage> {
  bool _loading = true;
  bool _syncing = false;
  String? _syncMessage;
  bool _syncMessageIsError = false;

  int _pendingCount = 0;
  int _conflictCount = 0;
  DateTime? _lastSyncAt;
  List<({String commandId, String command, String status, String? error})> _failures = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final store = await LocalStore.open();
    final pending = await store.pendingCommandCount();
    final conflicts = await store.conflictCount();
    final lastSync = await store.getLastSyncAt();
    final failures = await store.terminalFailures();
    if (!mounted) return;
    setState(() {
      _pendingCount = pending;
      _conflictCount = conflicts;
      _lastSyncAt = lastSync;
      _failures = failures;
      _loading = false;
    });
  }

  Future<void> _syncNow() async {
    if (_syncing) return;
    setState(() {
      _syncing = true;
      _syncMessage = null;
    });
    try {
      final store = await LocalStore.open();
      final result = await SyncRunner(store).run();
      if (!mounted) return;
      await _load();
      if (!mounted) return;

      if (result.hasTransportError) {
        setState(() {
          _syncMessage = 'تعذّرت المزامنة: ${result.transportError}';
          _syncMessageIsError = true;
        });
      } else if (result.upload.terminalFailures > 0) {
        setState(() {
          _syncMessage = 'تمت المزامنة مع ${result.upload.terminalFailures} عملية مرفوضة — التفاصيل تحت.';
          _syncMessageIsError = true;
        });
      } else if (result.hasWork) {
        final parts = <String>[];
        if (result.upload.applied > 0) parts.add('رُفع ${result.upload.applied} عملية');
        if (result.download.applied > 0) parts.add('نُزّل ${result.download.applied} تغيير');
        setState(() {
          _syncMessage = parts.isEmpty ? 'تمت المزامنة.' : 'تمت المزامنة — ${parts.join(' ، ')}.';
          _syncMessageIsError = false;
        });
      } else {
        setState(() {
          _syncMessage = 'البيانات محدّثة، لا يوجد تغييرات.';
          _syncMessageIsError = false;
        });
      }
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  String _statusLabel(String status) => switch (status) {
        'CONFLICT' => 'تعارض',
        'FAILED' => 'فشل',
        _ => status,
      };

  Color _statusColor(String status) => status == 'CONFLICT' ? Colors.orange.shade800 : Colors.red.shade700;

  @override
  Widget build(BuildContext context) {
    final failedCount = _failures.where((f) => f.status == 'FAILED').length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('لوحة تفاصيل المزامنة'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'تحديث',
            onPressed: _loading ? null : _load,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
                children: [
                  // ── ملخّص الحالة (Pending / Last Sync / Conflicts / Failed) ──
                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          icon: Icons.upload_rounded,
                          label: 'عمليات معلّقة',
                          value: '$_pendingCount',
                          color: _pendingCount > 0 ? Colors.blue.shade700 : Colors.green.shade700,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _StatCard(
                          icon: Icons.history_rounded,
                          label: 'آخر مزامنة',
                          value: formatSyncTime(_lastSyncAt),
                          color: Colors.black87,
                          valueFontSize: 13,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          icon: Icons.compare_arrows_rounded,
                          label: 'تعارضات',
                          value: '$_conflictCount',
                          color: _conflictCount > 0 ? Colors.orange.shade800 : Colors.green.shade700,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _StatCard(
                          icon: Icons.error_outline_rounded,
                          label: 'عمليات فاشلة',
                          value: '$failedCount',
                          color: failedCount > 0 ? Colors.red.shade700 : Colors.green.shade700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),

                  // ── زرار المزامنة اليدوية ────────────────────────────────
                  FilledButton.icon(
                    onPressed: _syncing ? null : _syncNow,
                    icon: _syncing
                        ? const SizedBox(
                            width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Icon(Icons.sync_rounded),
                    label: Text(_syncing ? 'جارِ المزامنة...' : 'مزامنة الآن'),
                    style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(46)),
                  ),
                  if (_syncMessage != null) ...[
                    const SizedBox(height: 10),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: _syncMessageIsError ? const Color(0xFFFDECEA) : const Color(0xFFE8F5E9),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _syncMessage!,
                        style: TextStyle(
                          color: _syncMessageIsError ? Colors.red.shade800 : Colors.green.shade800,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(height: 22),

                  // ── قائمة أخطاء المزامنة ─────────────────────────────────
                  Row(
                    children: [
                      const Text('أخطاء المزامنة',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                      const SizedBox(width: 8),
                      if (_failures.isNotEmpty)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.red.shade50,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text('${_failures.length}',
                              style: TextStyle(color: Colors.red.shade700, fontWeight: FontWeight.bold, fontSize: 12)),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (_failures.isEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Row(
                          children: [
                            Icon(Icons.check_circle_outline_rounded, color: Colors.green.shade700),
                            const SizedBox(width: 10),
                            const Expanded(
                              child: Text('لا يوجد عمليات مرفوضة من السيرفر حاليًا.'),
                            ),
                          ],
                        ),
                      ),
                    )
                  else
                    Card(
                      child: Column(
                        children: [
                          for (var i = 0; i < _failures.length; i++) ...[
                            if (i > 0) const Divider(height: 1),
                            ListTile(
                              leading: Icon(Icons.error_outline_rounded, color: _statusColor(_failures[i].status)),
                              title: Text(
                                _failures[i].command,
                                style: const TextStyle(fontWeight: FontWeight.bold),
                              ),
                              subtitle: Text(
                                _failures[i].error ?? 'بدون تفاصيل إضافية',
                                maxLines: 3,
                                overflow: TextOverflow.ellipsis,
                              ),
                              trailing: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: _statusColor(_failures[i].status).withOpacity(0.1),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: Text(
                                  _statusLabel(_failures[i].status),
                                  style: TextStyle(color: _statusColor(_failures[i].status), fontWeight: FontWeight.bold, fontSize: 12),
                                ),
                              ),
                              isThreeLine: true,
                            ),
                          ],
                        ],
                      ),
                    ),
                ],
              ),
            ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
    this.valueFontSize = 22,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color color;
  final double valueFontSize;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(height: 8),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: valueFontSize, fontWeight: FontWeight.w900, color: color),
            ),
            const SizedBox(height: 2),
            Text(label, style: const TextStyle(fontSize: 12, color: Colors.black54)),
          ],
        ),
      ),
    );
  }
}
