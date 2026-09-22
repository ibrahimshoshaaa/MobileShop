import 'dart:convert';
import 'dart:io';

import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

import 'auth_models.dart';

/// خطأ تسجيل الدخول.
class AuthException implements Exception {
  AuthException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// يدير تسجيل الدخول، حفظ الجلسة، وقراءتها عند بدء التطبيق.
class AuthService {
  AuthService._();
  static final AuthService instance = AuthService._();

  static const _timeout = Duration(seconds: 20);
  static const _sessionKey = 'account_session';

  Database? _db;
  AccountSession? _session;

  // ─── DB ──────────────────────────────────────────────────────────────────

  Future<Database> _getDb() async {
    _db ??= await openDatabase(
      join(await getDatabasesPath(), 'auth_session.db'),
      version: 1,
      onCreate: (db, _) => db.execute(
        'CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
      ),
    );
    return _db!;
  }

  Future<void> _save(String key, String value) async {
    final db = await _getDb();
    await db.insert('kv', {'key': key, 'value': value},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<String?> _read(String key) async {
    final db = await _getDb();
    final rows = await db.query('kv', where: 'key = ?', whereArgs: [key]);
    return rows.isEmpty ? null : rows.first['value'] as String;
  }

  Future<void> _delete(String key) async {
    final db = await _getDb();
    await db.delete('kv', where: 'key = ?', whereArgs: [key]);
  }

  // ─── Session ──────────────────────────────────────────────────────────────

  /// يحمّل الجلسة المحفوظة — null لو مفيش.
  Future<AccountSession?> loadSession() async {
    if (_session != null) return _session;
    final raw = await _read(_sessionKey);
    if (raw == null) return null;
    try {
      _session = AccountSession.fromJsonString(raw);
      return _session;
    } catch (_) {
      return null;
    }
  }

  AccountSession? get currentSession => _session;
  bool get isLoggedIn => _session != null;

  // ─── Login ───────────────────────────────────────────────────────────────

  /// تسجيل دخول: يبعت email+password للـ API، يرجع قائمة الفروع لو فيه أكتر من واحد.
  /// [onSelectBranch] بيتنادى لو فيه أكتر من فرع — بترجع الـ BranchInfo المختار.
  Future<AccountSession> login({
    required String apiUrl,
    required String email,
    required String password,
    required Future<BranchInfo> Function(List<BranchInfo>) onSelectBranch,
  }) async {
    final base = apiUrl.endsWith('/')
        ? apiUrl.substring(0, apiUrl.length - 1)
        : apiUrl;

    // 1) Login
    final loginData = await _post('$base/auth/login', {
      'email': email.trim(),
      'password': password,
    });

    final token = loginData['token'] as String? ??
        (throw AuthException('السيرفر لم يُرجع token.'));
    final tenantId = loginData['tenant_id'] as String? ??
        (throw AuthException('السيرفر لم يُرجع tenant_id.'));
    final accountId = loginData['account_id'] as String? ??
        (throw AuthException('السيرفر لم يُرجع account_id.'));
    final displayName = loginData['display_name'] as String? ?? email;

    // 2) جلب الفروع
    final branchesRaw = await _get('$base/branches', token: token);
    final branches = (branchesRaw['data'] as List? ?? [])
        .map((b) => BranchInfo.fromJson(b as Map<String, dynamic>))
        .toList();

    if (branches.isEmpty) {
      throw AuthException('حسابك ليس مرتبطًا بأي فرع. تواصل مع مدير النظام.');
    }

    // 3) اختيار الفرع
    final BranchInfo chosen;
    if (branches.length == 1) {
      chosen = branches.first;
    } else {
      chosen = await onSelectBranch(branches);
    }

    // 4) حفظ الجلسة
    _session = AccountSession(
      tenantId: tenantId,
      accountId: accountId,
      email: email.trim(),
      displayName: displayName,
      token: token,
      branchId: chosen.id,
      branchName: chosen.name,
      apiUrl: base,
    );
    await _save(_sessionKey, _session!.toJsonString());
    return _session!;
  }

  /// تسجيل خروج — يمسح الجلسة المحفوظة.
  Future<void> logout() async {
    _session = null;
    await _delete(_sessionKey);
  }

  // ─── HTTP helpers ─────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> _post(
    String url,
    Map<String, dynamic> body, {
    String? token,
  }) async {
    final client = HttpClient();
    try {
      final req = await client.postUrl(Uri.parse(url)).timeout(_timeout);
      req.headers.set('Content-Type', 'application/json');
      if (token != null) req.headers.set('Authorization', 'Bearer $token');
      final encoded = utf8.encode(jsonEncode(body));
      req.contentLength = encoded.length;
      req.add(encoded);
      final res = await req.close().timeout(_timeout);
      final raw = await res.transform(utf8.decoder).join();
      final json = jsonDecode(raw) as Map<String, dynamic>;
      if (res.statusCode == 401) throw AuthException('بيانات الدخول غير صحيحة.');
      if (res.statusCode == 403) throw AuthException('الحساب ليس لديه صلاحية الوصول.');
      if (res.statusCode >= 400) {
        final msg = (json['error'] as Map<String, dynamic>?)?['message'] as String?;
        throw AuthException(msg ?? 'خطأ من السيرفر (${res.statusCode}).');
      }
      return json;
    } on SocketException {
      throw AuthException('تعذّر الاتصال بـ $url — تحقق من عنوان السيرفر والاتصال بالإنترنت.');
    } on HttpException catch (e) {
      throw AuthException('خطأ HTTP: ${e.message}');
    } finally {
      client.close();
    }
  }

  Future<Map<String, dynamic>> _get(String url, {String? token}) async {
    final client = HttpClient();
    try {
      final req = await client.getUrl(Uri.parse(url)).timeout(_timeout);
      if (token != null) req.headers.set('Authorization', 'Bearer $token');
      final res = await req.close().timeout(_timeout);
      final raw = await res.transform(utf8.decoder).join();
      final json = jsonDecode(raw) as Map<String, dynamic>;
      if (res.statusCode >= 400) {
        final msg = (json['error'] as Map<String, dynamic>?)?['message'] as String?;
        throw AuthException(msg ?? 'خطأ من السيرفر (${res.statusCode}).');
      }
      return json;
    } on SocketException {
      throw AuthException('تعذّر الاتصال بالسيرفر.');
    } finally {
      client.close();
    }
  }
}
