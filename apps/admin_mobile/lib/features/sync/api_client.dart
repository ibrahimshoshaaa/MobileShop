import 'dart:convert';
import 'dart:io';

import '../auth/auth_models.dart';

/// Thrown for any failure talking to the backend API — network errors,
/// non-2xx HTTP responses, and `{"ok": false, "error": {...}}` bodies alike.
/// [code] carries the server's error code (e.g. `FORBIDDEN`,
/// `BRANCH_ACCESS_DENIED`) when the server sent one, so callers can branch
/// on it instead of parsing [message].
class ApiException implements Exception {
  ApiException(this.message, {this.code});
  final String message;
  final String? code;
  @override
  String toString() => message;
}

/// HTTP client for `backend/api_server` (see `backend/api_server/main.py`)
/// — the mobile-side counterpart of `apps/desktop/api_client.py`. Wraps the
/// read/write shapes the server exposes: `GET /query/{entity}`,
/// `GET /sales`, `GET /reports`, `POST /command`, `POST /sync/upload`,
/// `GET /sync/changes`.
///
/// This only builds and executes requests — it does not decide *when* to
/// call the server, cache results, or fall back to SQLite. That's for the
/// repositories that will use it (4.2 read wiring, 4.3 write wiring) and
/// the sync engine (5.1/5.2) to decide.
///
/// Nothing in the app talks to the network directly except this and
/// `AuthService` (`/auth/login`, `/branches`), which this deliberately
/// does not duplicate — a client is built from the session AuthService
/// already produced, via [ApiClient.fromSession].
class ApiClient {
  ApiClient({
    required this.baseUrl,
    required this.token,
    required this.branchId,
  });

  /// Builds a client from the session `AuthService.instance.currentSession`
  /// already holds after login (3.2) — the normal way to get one:
  /// `ApiClient.fromSession(AuthService.instance.currentSession!)`.
  factory ApiClient.fromSession(AccountSession session) => ApiClient(
        baseUrl: session.apiUrl,
        token: session.token,
        branchId: session.branchId,
      );

  final String baseUrl;
  final String token;
  final String branchId;

  static const _timeout = Duration(seconds: 20);

  // ─── Reads ──────────────────────────────────────────────────────────────

  /// `GET /query/{entity}` — the generic tenant/branch-scoped read endpoint
  /// covering every entity `backend/api_server/main.py` lists in
  /// `_QUERY_REPOS`: products, customers, suppliers, sales, purchases,
  /// expenses, maintenance, installments, wallets, ledger, audit,
  /// employees, installment-payments, maintenance-parts, branches, users,
  /// roles.
  Future<List<Map<String, dynamic>>> getEntity(String entity, {int limit = 100}) async {
    final data = await _get('/query/$entity', {
      'branch_id': branchId,
      'limit': '$limit',
    });
    return (data as List).cast<Map<String, dynamic>>();
  }

  Future<List<Map<String, dynamic>>> getProducts({int limit = 100}) =>
      getEntity('products', limit: limit);

  Future<List<Map<String, dynamic>>> getCustomers({int limit = 100}) =>
      getEntity('customers', limit: limit);

  Future<List<Map<String, dynamic>>> getSuppliers({int limit = 100}) =>
      getEntity('suppliers', limit: limit);

  Future<List<Map<String, dynamic>>> getWallets({int limit = 100}) =>
      getEntity('wallets', limit: limit);

  /// `GET /sales` — the server's dedicated sales read endpoint (kept
  /// separate from `/query/sales` for the desktop's Online mode); mirrored
  /// here rather than routed through [getEntity] for parity with
  /// `apps/desktop/api_client.py`.
  Future<List<Map<String, dynamic>>> getSales({int limit = 50}) async {
    final data = await _get('/sales', {
      'branch_id': branchId,
      'limit': '$limit',
    });
    return (data as List).cast<Map<String, dynamic>>();
  }

  /// `GET /reports` — server-computed report for `[start, end]`
  /// (`YYYY-MM-DD`, both optional). Shape matches `engine.reports_full`.
  Future<Map<String, dynamic>> getReports({String? start, String? end}) async {
    final data = await _get('/reports', {
      'branch_id': branchId,
      if (start != null) 'start': start,
      if (end != null) 'end': end,
    });
    return data as Map<String, dynamic>;
  }

  // ─── Writes ─────────────────────────────────────────────────────────────

  /// `POST /command` — a single command against the ERP engine
  /// (`backend/functions/services/erp_engine.py`), the same boundary
  /// `dispatch()` and every `backend/functions/commands/*.py` module uses.
  /// [commandId] must be caller-generated and stable across retries — the
  /// server is idempotent on it (a repeated id returns the original result
  /// instead of double-applying), which is exactly what the Upload Queue in
  /// 5.1 will rely on when it replays failed sends.
  Future<dynamic> command(
    String commandId,
    String commandName,
    Map<String, dynamic> payload,
  ) {
    return _post('/command', {
      'commandId': commandId,
      'command': commandName,
      'branchId': branchId,
      'payload': payload,
    });
  }

  /// `POST /sync/upload` — a batch of offline-generated commands, in the
  /// shape `SyncProtocol.upload` (`backend/functions/offline/protocol.py`)
  /// expects. Not called from anywhere yet — this is the endpoint 5.1's
  /// Upload Queue will drain into.
  Future<dynamic> syncUpload(List<Map<String, dynamic>> commands) {
    return _post('/sync/upload', {
      'branch_id': branchId,
      'commands': commands,
    });
  }

  /// `GET /sync/changes` — cursor-based pull of everything changed since
  /// [cursor] (`0` = from the beginning). Not called from anywhere yet —
  /// this is what 5.2's Download Queue will page through.
  Future<Map<String, dynamic>> syncChanges({int cursor = 0, int limit = 100}) async {
    final data = await _get('/sync/changes', {
      'branch_id': branchId,
      'cursor': '$cursor',
      'limit': '$limit',
    });
    return data as Map<String, dynamic>;
  }

  // ─── HTTP plumbing ────────────────────────────────────────────────────
  // Same dart:io HttpClient approach as AuthService._get/_post (no `http`
  // package dependency added just for this) and the same response-shape
  // handling as apps/desktop/api_client.py: every body is
  // `{"ok": true, "data": ...}` or `{"ok": false, "error": {...}}`.

  Future<dynamic> _get(String path, Map<String, String> query) async {
    final uri = Uri.parse('$baseUrl$path').replace(queryParameters: query);
    final client = HttpClient();
    try {
      final req = await client.getUrl(uri).timeout(_timeout);
      req.headers.set('Authorization', 'Bearer $token');
      final res = await req.close().timeout(_timeout);
      final raw = await res.transform(utf8.decoder).join();
      return _unwrap(res.statusCode, raw);
    } on SocketException {
      throw ApiException('تعذّر الاتصال بالسيرفر على $baseUrl.');
    } on HttpException catch (e) {
      throw ApiException('خطأ HTTP: ${e.message}');
    } finally {
      client.close();
    }
  }

  Future<dynamic> _post(String path, Map<String, dynamic> body) async {
    final uri = Uri.parse('$baseUrl$path');
    final client = HttpClient();
    try {
      final req = await client.postUrl(uri).timeout(_timeout);
      req.headers.set('Content-Type', 'application/json');
      req.headers.set('Authorization', 'Bearer $token');
      final encoded = utf8.encode(jsonEncode(body));
      req.contentLength = encoded.length;
      req.add(encoded);
      final res = await req.close().timeout(_timeout);
      final raw = await res.transform(utf8.decoder).join();
      return _unwrap(res.statusCode, raw);
    } on SocketException {
      throw ApiException('تعذّر الاتصال بالسيرفر على $baseUrl.');
    } on HttpException catch (e) {
      throw ApiException('خطأ HTTP: ${e.message}');
    } finally {
      client.close();
    }
  }

  /// Parses the server's `{"ok": ...}` envelope and either returns `data`
  /// or throws [ApiException] with the server's message/code when present,
  /// falling back to a status-code-based Arabic message otherwise (a 401
  /// here means the saved session/token is no longer valid — distinct from
  /// AuthService's 401 during login itself).
  dynamic _unwrap(int statusCode, String raw) {
    Map<String, dynamic> json;
    try {
      json = jsonDecode(raw) as Map<String, dynamic>;
    } catch (_) {
      throw ApiException('استجابة غير صالحة من السيرفر (كود $statusCode).');
    }
    if (json['ok'] == false || statusCode >= 400) {
      final error = json['error'] as Map<String, dynamic>?;
      final code = error?['code'] as String?;
      final message = error?['message'] as String? ??
          (statusCode == 401
              ? 'انتهت صلاحية الجلسة، سجّل الدخول مرة تانية.'
              : 'خطأ من السيرفر (كود $statusCode).');
      throw ApiException(message, code: code);
    }
    return json['data'];
  }
}
