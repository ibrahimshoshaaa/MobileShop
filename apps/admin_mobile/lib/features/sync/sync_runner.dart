import '../inventory/local_store.dart';
import 'download_queue.dart';
import 'upload_queue.dart';

/// Combined result of one [SyncRunner.run] cycle — what every caller
/// (app-start drain, Settings' quick "مزامنة الآن", the Sync Dashboard,
/// 5.3) builds its status message from.
class SyncRunResult {
  const SyncRunResult({required this.upload, required this.download});

  final UploadQueueResult upload;
  final DownloadQueueResult download;

  bool get hasTransportError => upload.transportError != null || download.hasError;
  String? get transportError => upload.transportError ?? download.transportError;
  bool get hasWork => upload.hasWork || download.applied > 0;
}

/// Runs one upload-then-download sync cycle and records when it last
/// happened, so every place that triggers a sync — main.dart's app-start
/// catch-up drain, Settings' manual "مزامنة الآن", the Sync Dashboard
/// (5.3) — shares one "آخر مزامنة" timestamp instead of each tracking (or
/// forgetting to track) its own. Before this, only Settings' `_syncNow`
/// ran upload then download at all; main.dart's app-start drain fired both
/// unawaited independently despite its comment saying "بعد الـ upload" —
/// fixed here as a side effect of centralizing this.
class SyncRunner {
  SyncRunner(this._store);
  final LocalStore _store;

  Future<SyncRunResult> run() async {
    final upload = await UploadQueue(_store).drain();
    final download = await DownloadQueue(_store).drain();
    final result = SyncRunResult(upload: upload, download: download);
    // "آخر مزامنة" يتسجل طالما فعليًا اتكلمنا مع السيرفر — حتى لو رجع
    // CONFLICT/FAILED لبعض الأوامر، أو مفيش تغييرات خالص. مش لو فشل
    // الاتصال بالكامل (transportError)، لأن وقتها معندناش سيرفر
    // اتكلمنا معاه فعلاً في الدورة دي.
    if (!result.hasTransportError) {
      await _store.saveLastSyncAt(DateTime.now());
    }
    return result;
  }
}
