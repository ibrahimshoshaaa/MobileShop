import 'dart:convert';
import 'dart:math';
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

/// Local offline-first store for the mobile app. Deliberately mirrors the
/// schema in backend/functions/persistence/sqlite_repository.py (records +
/// commands + outbox) so the two stay conceptually compatible when the real
/// upload/download sync protocol (see status doc: "Offline-to-Online
/// behavior") gets built — the shape of what's queued here should map
/// directly onto what that protocol will ship.
///
/// TODO once account linking / branch selection exist: replace
/// [defaultTenantId] / [defaultBranchId] with the values from the linked
/// account and selected branch instead of hardcoded placeholders.
class LocalStore {
  LocalStore._(this._db);
  final Database _db;

  static const defaultTenantId = 'LOCAL_TENANT';
  static const defaultBranchId = 'LOCAL_BRANCH';

  static Database? _cached;

  static Future<LocalStore> open() async {
    if (_cached == null) {
      final dbPath = p.join(await getDatabasesPath(), 'mobile_shop_erp.db');
      _cached = await openDatabase(
        dbPath,
        version: 2,
        onConfigure: (db) async {
          await db.execute('PRAGMA foreign_keys = ON');
        },
        onCreate: (db, version) async {
          await db.execute('''
            CREATE TABLE records (
              entity TEXT NOT NULL,
              record_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              branch_id TEXT NOT NULL,
              payload TEXT NOT NULL,
              version INTEGER NOT NULL DEFAULT 1,
              PRIMARY KEY(entity, record_id)
            );
          ''');
          await db.execute('''
            CREATE TABLE commands (
              command_id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              branch_id TEXT NOT NULL,
              command TEXT NOT NULL,
              payload TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'PENDING',
              error TEXT,
              attempts INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
          ''');
          await db.execute('''
            CREATE TABLE outbox (
              command_id TEXT PRIMARY KEY,
              next_attempt_at TEXT,
              last_error TEXT,
              FOREIGN KEY(command_id) REFERENCES commands(command_id) ON DELETE CASCADE
            );
          ''');
          await db.execute('CREATE INDEX idx_records_tenant_branch ON records(tenant_id, branch_id, entity)');
          await db.execute('CREATE INDEX idx_commands_tenant_status ON commands(tenant_id, status, created_at)');
          await db.execute('''
            CREATE TABLE kv (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
          ''');
        },
        onUpgrade: (db, oldVersion, newVersion) async {
          if (oldVersion < 2) {
            await db.execute('''
              CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
              );
            ''');
          }
        },
      );
    }
    return LocalStore._(_cached!);
  }

  /// Atomically insert/update a scoped local record with optimistic
  /// concurrency, same semantics as the Python `upsert_record`. Returns the
  /// new version. Throws [StaleVersionException] if [expectedVersion]
  /// doesn't match what's stored (someone else changed it first).
  Future<int> upsertRecord({
    required String entity,
    required String recordId,
    required Map<String, dynamic> payload,
    String tenantId = defaultTenantId,
    String branchId = defaultBranchId,
    int? expectedVersion,
  }) async {
    return _db.transaction((txn) async {
      final rows = await txn.query('records',
          where: 'entity = ? AND record_id = ?', whereArgs: [entity, recordId]);
      final encoded = jsonEncode(payload);
      if (rows.isNotEmpty) {
        final current = rows.first;
        if (current['tenant_id'] != tenantId || current['branch_id'] != branchId) {
          throw StateError('record belongs to another tenant/branch');
        }
        final currentVersion = current['version'] as int;
        if (expectedVersion != null && expectedVersion != currentVersion) {
          throw StaleVersionException(entity: entity, recordId: recordId, currentVersion: currentVersion);
        }
        final newVersion = currentVersion + 1;
        await txn.update('records', {'payload': encoded, 'version': newVersion},
            where: 'entity = ? AND record_id = ?', whereArgs: [entity, recordId]);
        return newVersion;
      }
      if (expectedVersion != null && expectedVersion != 0) {
        throw StaleVersionException(entity: entity, recordId: recordId, currentVersion: 0);
      }
      await txn.insert('records', {
        'entity': entity,
        'record_id': recordId,
        'tenant_id': tenantId,
        'branch_id': branchId,
        'payload': encoded,
        'version': 1,
      });
      return 1;
    });
  }

  Future<({Map<String, dynamic> payload, int version})?> getRecord({
    required String entity,
    required String recordId,
    String tenantId = defaultTenantId,
  }) async {
    final rows = await _db.query('records',
        where: 'entity = ? AND record_id = ? AND tenant_id = ?', whereArgs: [entity, recordId, tenantId]);
    if (rows.isEmpty) return null;
    return (payload: jsonDecode(rows.first['payload'] as String) as Map<String, dynamic>, version: rows.first['version'] as int);
  }

  Future<List<({Map<String, dynamic> payload, int version})>> listRecords({
    required String entity,
    String tenantId = defaultTenantId,
    String? branchId,
  }) async {
    final where = StringBuffer('entity = ? AND tenant_id = ?');
    final args = <Object?>[entity, tenantId];
    if (branchId != null) {
      where.write(' AND branch_id = ?');
      args.add(branchId);
    }
    final rows = await _db.query('records', where: where.toString(), whereArgs: args, orderBy: 'record_id');
    return rows
        .map((r) => (payload: jsonDecode(r['payload'] as String) as Map<String, dynamic>, version: r['version'] as int))
        .toList();
  }

  /// Queue a command in the offline outbox. Idempotent on [commandId]: if
  /// it's already been submitted, just returns its current status instead
  /// of inserting a duplicate — mirrors the Python `submit_command` guard.
  Future<String> queueCommand({
    required String commandId,
    required String command,
    required Map<String, dynamic> payload,
    String tenantId = defaultTenantId,
    String branchId = defaultBranchId,
  }) async {
    return _db.transaction((txn) async {
      final existing = await txn.query('commands', where: 'command_id = ?', whereArgs: [commandId]);
      if (existing.isNotEmpty) {
        return existing.first['status'] as String;
      }
      await txn.insert('commands', {
        'command_id': commandId,
        'tenant_id': tenantId,
        'branch_id': branchId,
        'command': command,
        'payload': jsonEncode(payload),
        'status': 'PENDING',
      });
      await txn.insert('outbox', {'command_id': commandId});
      return 'PENDING';
    });
  }

  /// Marks a queued command as already delivered to the server — used by
  /// the 4.3 "push now, best effort" write path (see
  /// `features/sync/online_push.dart`) right after a direct `/command` call
  /// for it succeeds. Removing it from `outbox` (not just flipping
  /// `commands.status`) is what actually keeps it from being resent: the
  /// future Upload Queue (5.1) will drain `outbox`, not `commands`, so a row
  /// no longer there is a row it will never see. `commands` itself is kept
  /// (status set to `SYNCED`) purely as a local audit trail of what already
  /// reached the server.
  Future<void> markCommandSynced(String commandId) async {
    await _db.transaction((txn) async {
      await txn.delete('outbox', where: 'command_id = ?', whereArgs: [commandId]);
      await txn.update(
        'commands',
        {'status': 'SYNCED', 'updated_at': DateTime.now().toIso8601String()},
        where: 'command_id = ?',
        whereArgs: [commandId],
      );
    });
  }

  /// Count of commands still waiting to reach the server (i.e. still in
  /// `outbox`) — this device only ever has one meaningfully active
  /// tenant/branch at a time (see [UploadQueue]'s doc comment), so this
  /// deliberately doesn't filter by tenant the way it used to.
  Future<int> pendingCommandCount() async {
    final result = await _db.rawQuery("SELECT COUNT(*) as c FROM outbox");
    return Sqflite.firstIntValue(result) ?? 0;
  }

  /// One PENDING command whose retry backoff (if any) has already elapsed —
  /// everything the Upload Queue (5.1, `features/sync/upload_queue.dart`)
  /// needs to build one `/sync/upload` envelope for it. `tenantId`/
  /// `branchId` are deliberately not included here: they're read off the
  /// *current* session at drain time instead of what's stored on the row
  /// (see the doc comment on [UploadQueue.drain] for why).
  Future<List<({String commandId, String command, Map<String, dynamic> payload, int attempts})>> listDueOutboxCommands({
    int limit = 100,
  }) async {
    final rows = await _db.rawQuery('''
      SELECT c.command_id, c.command, c.payload, c.attempts
      FROM outbox o
      JOIN commands c ON c.command_id = o.command_id
      WHERE o.next_attempt_at IS NULL OR o.next_attempt_at <= ?
      ORDER BY c.created_at
      LIMIT ?
    ''', [DateTime.now().toIso8601String(), limit]);
    return rows
        .map((r) => (
              commandId: r['command_id'] as String,
              command: r['command'] as String,
              payload: jsonDecode(r['payload'] as String) as Map<String, dynamic>,
              attempts: r['attempts'] as int,
            ))
        .toList();
  }

  /// Records a RETRYABLE result from the server: bumps `attempts` and pushes
  /// `outbox.next_attempt_at` out with exponential backoff (10s, 20s, 40s,
  /// ... capped at 1 hour) so a flaky connection or a transient server error
  /// doesn't get hammered every drain — [listDueOutboxCommands] simply won't
  /// return this row again until that time passes. Stays PENDING/in the
  /// outbox either way; nothing here is terminal.
  Future<void> scheduleRetry(String commandId, String error) async {
    await _db.transaction((txn) async {
      final rows = await txn.query('commands', columns: ['attempts'], where: 'command_id = ?', whereArgs: [commandId]);
      if (rows.isEmpty) return;
      final attempts = (rows.first['attempts'] as int) + 1;
      final backoffSeconds = min(3600, 10 * (1 << min(attempts, 9)));
      final nextAttempt = DateTime.now().add(Duration(seconds: backoffSeconds)).toIso8601String();
      await txn.update(
        'commands',
        {'attempts': attempts, 'error': error, 'updated_at': DateTime.now().toIso8601String()},
        where: 'command_id = ?',
        whereArgs: [commandId],
      );
      await txn.update(
        'outbox',
        {'next_attempt_at': nextAttempt, 'last_error': error},
        where: 'command_id = ?',
        whereArgs: [commandId],
      );
    });
  }

  /// Records a terminal (non-retryable) result — CONFLICT or FAILED. The
  /// server has definitively rejected this exact command and resending it
  /// unchanged will never succeed (a stale version, a domain rule violation,
  /// an idempotency-key reuse with different content), so it's removed from
  /// `outbox` — the queue stops touching it — while `commands` keeps the row
  /// with its [status]/[error] as a local audit trail the person can be
  /// shown (see Settings' Cloud Account section).
  Future<void> markCommandTerminalFailure(String commandId, String status, String? error) async {
    await _db.transaction((txn) async {
      await txn.delete('outbox', where: 'command_id = ?', whereArgs: [commandId]);
      await txn.update(
        'commands',
        {'status': status, 'error': error, 'updated_at': DateTime.now().toIso8601String()},
        where: 'command_id = ?',
        whereArgs: [commandId],
      );
    });
  }

  /// Commands the Upload Queue gave up on (CONFLICT/FAILED) — surfaced in
  /// Settings so a rejected sale/expense/etc. doesn't just silently vanish
  /// from sync forever with no way for the person to notice.
  Future<List<({String commandId, String command, String status, String? error})>> terminalFailures({
    int limit = 50,
  }) async {
    final rows = await _db.query(
      'commands',
      where: "status IN ('CONFLICT','FAILED')",
      orderBy: 'updated_at DESC',
      limit: limit,
    );
    return rows
        .map((r) => (
              commandId: r['command_id'] as String,
              command: r['command'] as String,
              status: r['status'] as String,
              error: r['error'] as String?,
            ))
        .toList();
  }

  /// Count of commands the server rejected as a genuine conflict (stale
  /// version / idempotency-key reuse with different content) — kept apart
  /// from a plain `FAILED` count because a conflict usually means "someone
  /// else changed this first" (something the person can investigate),
  /// while a bare failure is more often a domain-rule rejection. Used by
  /// the Sync Dashboard (5.3).
  Future<int> conflictCount() async {
    final result = await _db.rawQuery("SELECT COUNT(*) as c FROM commands WHERE status = 'CONFLICT'");
    return Sqflite.firstIntValue(result) ?? 0;
  }

  /// Dumps every row of the `records` table (every entity: products, sales,
  /// customers, etc.) as plain maps, ready to be JSON-encoded for a backup
  /// file. Used by the Settings > Export Backup feature.
  Future<List<Map<String, dynamic>>> exportAllRecords() async {
    final rows = await _db.query('records', orderBy: 'entity, record_id');
    return rows
        .map((r) => {
              'entity': r['entity'],
              'record_id': r['record_id'],
              'tenant_id': r['tenant_id'],
              'branch_id': r['branch_id'],
              'payload': jsonDecode(r['payload'] as String),
              'version': r['version'],
            })
        .toList();
  }

  /// Writes a record back exactly as given (entity/id/tenant/branch/version),
  /// replacing whatever is already stored for that key. Unlike [upsertRecord]
  /// this skips the optimistic-concurrency check, because restoring a backup
  /// is an explicit "make the device match this file" action chosen by the
  /// user, not a concurrent edit that needs conflict detection.
  Future<void> restoreRecord({
    required String entity,
    required String recordId,
    required String tenantId,
    required String branchId,
    required Map<String, dynamic> payload,
    required int version,
  }) async {
    await _db.insert(
      'records',
      {
        'entity': entity,
        'record_id': recordId,
        'tenant_id': tenantId,
        'branch_id': branchId,
        'payload': jsonEncode(payload),
        'version': version,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Deletes every row in `records`. Used right before a full backup
  /// restore so the device ends up with exactly what's in the backup file,
  /// not a mix of old and restored data.
  // ─── Sync Cursor (5.2) ───────────────────────────────────────────────────

  /// آخر cursor تم تنزيل changes حتى هذا الرقم من السيرفر.
  /// `0` يعني لم يتم تنزيل أي شيء بعد (أول مرة).
  Future<int> getSyncCursor() async {
    final rows = await _db.query('kv', where: 'key = ?', whereArgs: ['sync_cursor']);
    if (rows.isEmpty) return 0;
    return int.tryParse(rows.first['value'] as String) ?? 0;
  }

  /// يحفظ الـ cursor بعد كل صفحة ناجحة من `/sync/changes`.
  Future<void> saveSyncCursor(int cursor) async {
    await _db.insert(
      'kv',
      {'key': 'sync_cursor', 'value': '$cursor'},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// يمسح الـ cursor — يستخدم عند تسجيل الخروج عشان الدخول الجديد
  /// يبدأ من الأول (لو كان حساب مختلف أو فرع مختلف).
  Future<void> resetSyncCursor() async {
    await _db.delete('kv', where: 'key = ?', whereArgs: ['sync_cursor']);
  }

  /// آخر وقت اتكلم فيه الجهاز مع السيرفر بنجاح (Sync Dashboard, 5.3) —
  /// يتسجل من [SyncRunner] بعد أي دورة upload+download وصلت فعليًا
  /// للسيرفر (حتى لو فيها CONFLICT/FAILED لبعض الأوامر)، مش بس لما فيه
  /// تغييرات فعلية. `null` يعني لسه ما حصلتش أي مزامنة على الجهاز ده.
  Future<DateTime?> getLastSyncAt() async {
    final rows = await _db.query('kv', where: 'key = ?', whereArgs: ['last_sync_at']);
    if (rows.isEmpty) return null;
    return DateTime.tryParse(rows.first['value'] as String);
  }

  Future<void> saveLastSyncAt(DateTime time) async {
    await _db.insert(
      'kv',
      {'key': 'last_sync_at', 'value': time.toIso8601String()},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// يمسح وقت آخر مزامنة — يستخدم عند تسجيل الخروج زي [resetSyncCursor]
  /// بالظبط، عشان حساب جديد يبدأ بدون تاريخ مزامنة يخص حساب غيره.
  Future<void> resetLastSyncAt() async {
    await _db.delete('kv', where: 'key = ?', whereArgs: ['last_sync_at']);
  }

  Future<void> clearAllRecords() async {
    await _db.delete('records');
  }
}

class StaleVersionException implements Exception {
  StaleVersionException({required this.entity, required this.recordId, required this.currentVersion});
  final String entity;
  final String recordId;
  final int currentVersion;
  @override
  String toString() =>
      'تعذّر الحفظ: تم تعديل "$recordId" من جهاز آخر في الوقت نفسه. أعد فتح الصنف وحاول مجددًا.';
}
