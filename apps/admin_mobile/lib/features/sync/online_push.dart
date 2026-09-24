import '../auth/auth_service.dart';
import '../inventory/local_store.dart';
import 'api_client.dart';

/// 4.3 — "رفع البيانات (Sales / Expenses / Maintenance / Installments)
/// للسيرفر". For the specific write operations backend/functions/api/
/// dispatch.py actually exposes a command for, this is called right after
/// the existing local write + [LocalStore.queueCommand] (which stays
/// exactly as it was — every write still lands on-device first and is
/// still queued in the offline outbox, unchanged). It then makes one
/// best-effort attempt to also submit that same command to the server
/// immediately, using the *same* [commandId] the caller just queued.
///
/// Why the same id matters: the server is idempotent on command id (see
/// `backend/api_server/main.py`'s module docstring) — a repeated id
/// returns the original result instead of double-applying. Reusing it here
/// means a successful push now and a later 5.1 Upload Queue replay of the
/// same outbox row are the same idempotency key, so there is never a risk
/// of two server-side records for one local write, even after 5.1 exists.
///
/// Never throws. Offline-first means the local write this runs after has
/// already committed and must never be undone by a network hiccup, a
/// logged-out session, or a validation mismatch between the local and
/// server models (see the callers in sqlite_*_repository.dart for the
/// known cases where that happens, e.g. CREDIT sale payments). Any
/// failure just leaves the command PENDING in the outbox — exactly the
/// same state it would be in if this helper didn't exist at all — for
/// 5.1's retry logic to pick up once it's built.
Future<void> pushCommandOnline(
  LocalStore store,
  String commandId,
  String command,
  Map<String, dynamic> payload,
) async {
  final session = AuthService.instance.currentSession;
  if (session == null) return; // offline — stays queued for 5.1.
  try {
    await ApiClient.fromSession(session).command(commandId, command, payload);
    await store.markCommandSynced(commandId);
  } on ApiException {
    // Best effort only. Deliberately swallowed — see the doc comment above.
  }
}
