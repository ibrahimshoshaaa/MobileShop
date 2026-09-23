/// Formats a past [DateTime] as a short Arabic relative string for sync UI
/// (Settings' quick summary, the Sync Dashboard). No `intl` dependency —
/// same "stdlib only where reasonable" approach as [ApiClient].
String formatSyncTime(DateTime? time) {
  if (time == null) return 'لم تتم أي مزامنة بعد';
  final diff = DateTime.now().difference(time);
  if (diff.isNegative || diff.inSeconds < 5) return 'الآن';
  if (diff.inMinutes < 1) return 'منذ ${diff.inSeconds} ثانية';
  if (diff.inHours < 1) return 'منذ ${diff.inMinutes} دقيقة';
  if (diff.inDays < 1) return 'منذ ${diff.inHours} ساعة';
  if (diff.inDays < 30) return 'منذ ${diff.inDays} يوم';
  final two = (int n) => n.toString().padLeft(2, '0');
  return 'في ${two(time.day)}/${two(time.month)}/${time.year}';
}
