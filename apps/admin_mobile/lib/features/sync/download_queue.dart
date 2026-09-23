import '../inventory/local_store.dart';
import '../auth/auth_service.dart';
import 'api_client.dart';

/// نتيجة drain واحدة للـ Download Queue.
class DownloadQueueResult {
  const DownloadQueueResult({
    required this.applied,
    required this.pages,
    this.transportError,
  });

  /// عدد الـ changes اللي اتطبّقوا على LocalStore.
  final int applied;

  /// عدد الصفحات اللي اتجلبت من السيرفر.
  final int pages;

  /// لو انقطع الاتصال أو رجع خطأ من السيرفر — اللي اتطبّق قبله بيتحفظ.
  final String? transportError;

  bool get hasError => transportError != null;
  bool get isEmpty => applied == 0 && !hasError;
}

/// 5.2 — Download Queue: Cursor Tracking + Changes Fetching.
///
/// بيجيب كل التغييرات اللي حصلت على السيرفر منذ آخر cursor محفوظ
/// (أو من الأول لو أول مرة)، وبيطبّقها على [LocalStore] عبر [upsertRecord].
///
/// الـ cursor بيتحفظ في جدول `kv` في نفس DB الـ LocalStore —
/// بنستخدم نفس جدول الـ [LocalStore] ونضيف table بسيطة للـ kv
/// بدل ما نفتح DB تاني، عشان نفضل في transaction واحد.
///
/// **الفلسفة:** كل change هو `COMMAND_APPLIED` event — payload بتاعته هو
/// نتيجة الأمر زي ما السيرفر حفظه (مثلاً Product/Customer/Sale object).
/// [DownloadQueue] بيحوّل كل change لـ [upsertRecord] تلقائياً حسب
/// `entity_type` الموجود في الـ payload (لو موجود) أو حسب الـ `event_type`.
///
/// لو السيرفر رجّع `has_more: true`، بيكمّل صفحة صفحة لحد ما يخلص أو
/// يوقع خطأ. الـ cursor بيتحدّث بعد كل صفحة ناجحة — يعني لو انقطع
/// الإنترنت في النص، المرة الجاية هتكمّل من آخر نقطة وصل ليها.
class DownloadQueue {
  DownloadQueue(this._store);
  final LocalStore _store;

  static const _pageSize = 100;

  /// ينزّل كل التغييرات الجديدة من السيرفر ويطبّقها محليًا.
  /// No-op لو مفيش session نشطة.
  Future<DownloadQueueResult> drain() async {
    final session = AuthService.instance.currentSession;
    if (session == null || session.token.isEmpty) {
      return const DownloadQueueResult(applied: 0, pages: 0);
    }

    final client = ApiClient.fromSession(session);
    var cursor = await _store.getSyncCursor();
    var totalApplied = 0;
    var pages = 0;

    while (true) {
      Map<String, dynamic> result;
      try {
        result = await client.syncChanges(cursor: cursor, limit: _pageSize);
      } on ApiException catch (e) {
        return DownloadQueueResult(
          applied: totalApplied,
          pages: pages,
          transportError: e.message,
        );
      } catch (e) {
        return DownloadQueueResult(
          applied: totalApplied,
          pages: pages,
          transportError: e.toString(),
        );
      }

      final changes = (result['changes'] as List? ?? [])
          .cast<Map<String, dynamic>>();
      final nextCursor = (result['next_cursor'] as num?)?.toInt() ?? cursor;
      final hasMore = result['has_more'] as bool? ?? false;

      // طبّق كل change
      for (final change in changes) {
        await _applyChange(change, session.tenantId, session.branchId);
        totalApplied++;
      }

      // حفظ الـ cursor بعد كل صفحة — عشان لو انقطع الإنترنت نكمل من هنا
      if (nextCursor > cursor) {
        await _store.saveSyncCursor(nextCursor);
        cursor = nextCursor;
      }

      pages++;

      if (!hasMore || changes.isEmpty) break;
    }

    return DownloadQueueResult(applied: totalApplied, pages: pages);
  }

  /// يطبّق change واحد على LocalStore.
  ///
  /// كل COMMAND_APPLIED event فيه payload هو نتيجة الأمر من السيرفر.
  /// بنستخرج الـ entity_type والـ id من الـ payload ونعمل upsertRecord.
  Future<void> _applyChange(
    Map<String, dynamic> change,
    String tenantId,
    String branchId,
  ) async {
    final eventType = change['event_type'] as String? ?? '';
    if (eventType != 'COMMAND_APPLIED') return; // skip غير المهم

    final payload = change['payload'];
    if (payload == null) return;

    // الـ payload ممكن يكون Map مباشر أو map فيه entity و data
    if (payload is Map<String, dynamic>) {
      // حاول تستخرج entity_type و id
      final entityType = _guessEntity(payload);
      final recordId = _guessId(payload);
      if (entityType == null || recordId == null) return;

      try {
        await _store.upsertRecord(
          entity: entityType,
          recordId: recordId,
          tenantId: tenantId,
          branchId: branchId,
          payload: payload,
          expectedVersion: null, // last-write-wins من السيرفر
        );
      } on StaleVersionException {
        // السيرفر دايمًا أحق — نتجاهل الـ stale error وسيب المحلي زي ما هو
        // (الـ upsertRecord بيتحقق من version، بس في الـ Download
        //  السيرفر هو المصدر الحقيقي — لو المحلي أحدث سيبه)
      }
    }
  }

  /// يحاول يحدّد entity type من الـ payload.
  /// السيرفر بيحط أحيانًا `entity_type` أو ممكن نستنتجه من الحقول الموجودة.
  String? _guessEntity(Map<String, dynamic> payload) {
    // لو السيرفر بعت entity_type صريح
    final explicit = payload['entity_type'] as String?;
    if (explicit != null && explicit.isNotEmpty) return explicit;

    // استنتاج من الحقول المميزة
    if (payload.containsKey('product_type') || payload.containsKey('sku')) {
      return 'products';
    }
    if (payload.containsKey('wallet_type')) return 'wallets';
    if (payload.containsKey('device') && payload.containsKey('problem')) {
      return 'maintenance';
    }
    if (payload.containsKey('term_months') || payload.containsKey('base_financed')) {
      return 'installments';
    }
    if (payload.containsKey('subtotal') || payload.containsKey('items')) {
      return 'sales';
    }
    if (payload.containsKey('category') && payload.containsKey('amount') &&
        !payload.containsKey('items')) {
      return 'expenses';
    }
    if (payload.containsKey('phone') && !payload.containsKey('branch_ids')) {
      return 'customers';
    }
    if (payload.containsKey('branch_ids')) return 'suppliers';

    return null;
  }

  /// يستخرج record id من الـ payload.
  String? _guessId(Map<String, dynamic> payload) {
    final id = payload['id'];
    if (id is String && id.isNotEmpty) return id;
    return null;
  }
}
