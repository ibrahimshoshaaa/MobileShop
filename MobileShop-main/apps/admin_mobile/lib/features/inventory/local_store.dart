import 'dart:convert';
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
        version: 1,
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

  Future<int> pendingCommandCount({String tenantId = defaultTenantId}) async {
    final result = await _db.rawQuery(
        "SELECT COUNT(*) as c FROM commands WHERE tenant_id = ? AND status = 'PENDING'", [tenantId]);
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
