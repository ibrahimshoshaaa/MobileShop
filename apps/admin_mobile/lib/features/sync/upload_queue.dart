import '../auth/auth_service.dart';
import '../inventory/local_store.dart';
import 'api_client.dart';

/// 5.1 — Upload Queue. Drains [LocalStore]'s offline `outbox` (every local
/// write, in every feature, has queued itself there via
/// [LocalStore.queueCommand] since long before 4.3 existed) by batching
/// PENDING commands into `POST /sync/upload` calls, using exactly the
/// idempotency/conflict/retry contract `backend/functions/offline/
/// protocol.py`'s `SyncProtocol.upload` already implements server-side:
/// each command comes back as one of APPLIED / CONFLICT / FAILED /
/// RETRYABLE, and this maps each straight onto what [LocalStore] already
/// has for exactly this purpose.
///
/// This is the general-purpose catch-up path underneath 4.3's immediate
/// best-effort push (`features/sync/online_push.dart`): whatever 4.3
/// couldn't push at write-time — device was offline, the immediate call
/// failed, or the write happened under an entirely different app session —
/// stays queued exactly as it always has, and this is what actually
/// retries it, with the backoff/retry handling 4.3 deliberately left out.
///
/// Envelope tenant/branch: [LocalStore.queueCommand] stores whatever
/// tenant/branch defaults were active when a command was queued (often the
/// offline placeholders `LocalStore.defaultTenantId`/`defaultBranchId`,
/// since most writes happen with no requirement to be logged in). Rather
/// than rely on that, every envelope built here is stamped with the
/// *current* session's real `tenantId`/`branchId` — the server only checks
/// that an envelope's tenant/branch match the caller's own claims/branch
/// anyway (see `sync_upload_endpoint` in `backend/api_server/main.py`), and
/// this device only ever has one meaningfully "active" account/branch at a
/// time (there's no local multi-tenant or multi-branch concept yet — see
/// the TODO on `LocalStore.defaultTenantId`), so this is the correct
/// mapping without having to first go back and fix every call site that
/// queues a command.
class UploadQueueResult {
  const UploadQueueResult({
    required this.applied,
    required this.retryable,
    required this.terminalFailures,
    this.transportError,
  });

  final int applied;
  final int retryable;
  final int terminalFailures;

  /// Set when a whole batch couldn't even reach the server (offline, DNS,
  /// timeout, expired session) — none of the per-command counts above
  /// apply then, since no individual result was ever returned for that
  /// batch. Whatever was drained in *earlier* batches this same call still
  /// counts normally.
  final String? transportError;

  int get attempted => applied + retryable + terminalFailures;
  bool get hasWork => attempted > 0 || transportError != null;
}

class UploadQueue {
  UploadQueue(this._store);
  final LocalStore _store;

  /// Matches `SyncProtocol.upload`'s own `limit` parameter — sending more
  /// than this in one request raises `SYNC_BATCH_TOO_LARGE` server-side.
  static const _batchSize = 100;

  /// Drains everything currently due, one batch of [_batchSize] at a time,
  /// stopping when nothing due is left or a batch hits a transport error
  /// (no point immediately retrying the same dead connection in the same
  /// call — the next scheduled/manual drain will pick it back up). No-op,
  /// returning all zeros, when there's no active session: exactly 4.3's
  /// "offline stays queued" behavior, just centralized here too.
  Future<UploadQueueResult> drain() async {
    final session = AuthService.instance.currentSession;
    if (session == null) {
      return const UploadQueueResult(applied: 0, retryable: 0, terminalFailures: 0);
    }

    var applied = 0, retryable = 0, terminalFailures = 0;
    while (true) {
      final due = await _store.listDueOutboxCommands(limit: _batchSize);
      if (due.isEmpty) break;

      final envelopes = [
        for (final cmd in due)
          {
            'command_id': cmd.commandId,
            'tenant_id': session.tenantId,
            'branch_id': session.branchId,
            'command': cmd.command,
            'payload': cmd.payload,
          },
      ];

      List<dynamic> results;
      try {
        final data = await ApiClient.fromSession(session).syncUpload(envelopes) as Map<String, dynamic>;
        results = data['results'] as List<dynamic>;
      } on ApiException catch (e) {
        return UploadQueueResult(
          applied: applied,
          retryable: retryable,
          terminalFailures: terminalFailures,
          transportError: e.toString(),
        );
      }

      for (final raw in results) {
        final result = raw as Map<String, dynamic>;
        final commandId = result['command_id'] as String;
        switch (result['status'] as String) {
          case 'APPLIED':
            await _store.markCommandSynced(commandId);
            applied++;
            break;
          case 'RETRYABLE':
            await _store.scheduleRetry(commandId, (result['error_code'] as String?) ?? 'TEMPORARY_UNAVAILABLE');
            retryable++;
            break;
          default: // CONFLICT or FAILED — both terminal, see markCommandTerminalFailure's doc comment.
            await _store.markCommandTerminalFailure(commandId, result['status'] as String, result['error_code'] as String?);
            terminalFailures++;
            break;
        }
      }

      // Fewer than a full batch came back due means the outbox is now
      // empty of anything ready to try — stop instead of looping forever.
      if (due.length < _batchSize) break;
    }
    return UploadQueueResult(applied: applied, retryable: retryable, terminalFailures: terminalFailures);
  }
}
