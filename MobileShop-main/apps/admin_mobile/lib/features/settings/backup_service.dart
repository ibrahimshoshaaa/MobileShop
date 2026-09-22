import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../inventory/local_store.dart';

/// Chosen backup format: **JSON**, not a copy of the raw SQLite file.
///
/// Why JSON and not SQLite:
/// - The on-device schema (see [LocalStore]) is a generic
///   `records(entity, record_id, payload, version)` table used for every
///   entity, so a JSON dump of those rows is already a complete, lossless
///   backup — there's no relational structure a flat file copy would
///   preserve that JSON doesn't.
/// - JSON is human-readable and safe to inspect/diff, survives being
///   emailed or put in cloud storage, and doesn't depend on both devices
///   running compatible SQLite/sqflite versions the way a raw `.db` file
///   copy would.
/// - It matches the shape the future sync protocol (Stage 4/5 of the plan)
///   will already speak, since that's also record/version based.
class BackupPayload {
  const BackupPayload({
    required this.schemaVersion,
    required this.exportedAt,
    required this.records,
  });

  factory BackupPayload.fromJson(Map<String, dynamic> json) {
    final rawRecords = json['records'];
    if (rawRecords is! List) {
      throw const FormatException('ملف النسخة الاحتياطية غير صالح: لا يحتوي على بيانات.');
    }
    return BackupPayload(
      schemaVersion: json['schemaVersion'] as int? ?? 1,
      exportedAt: DateTime.tryParse(json['exportedAt'] as String? ?? '') ?? DateTime.now(),
      records: rawRecords.cast<Map<String, dynamic>>(),
    );
  }

  final int schemaVersion;
  final DateTime exportedAt;
  final List<Map<String, dynamic>> records;

  Map<String, dynamic> toJson() => {
        'app': 'mobile_shop_admin',
        'schemaVersion': schemaVersion,
        'exportedAt': exportedAt.toIso8601String(),
        'records': records,
      };
}

class BackupImportResult {
  const BackupImportResult({required this.recordCount, required this.exportedAt});
  final int recordCount;
  final DateTime exportedAt;
}

/// Reads/writes [BackupPayload]s to disk on top of [LocalStore]. Used by
/// the Settings > النسخ الاحتياطي section (Export/Import Backup).
class BackupService {
  BackupService(this._store);
  final LocalStore _store;

  static const _currentSchemaVersion = 1;

  Future<BackupPayload> _buildPayload() async {
    final records = await _store.exportAllRecords();
    return BackupPayload(
      schemaVersion: _currentSchemaVersion,
      exportedAt: DateTime.now(),
      records: records,
    );
  }

  /// Builds the backup and writes it to a timestamped `.json` file under
  /// the app's documents directory. Returns the file so the caller can
  /// share it (e.g. via the share sheet) or show its path.
  Future<File> exportToFile() async {
    final payload = await _buildPayload();
    final dir = await getApplicationDocumentsDirectory();
    final backupsDir = Directory(p.join(dir.path, 'backups'));
    if (!await backupsDir.exists()) {
      await backupsDir.create(recursive: true);
    }
    final stamp = payload.exportedAt.toIso8601String().replaceAll(RegExp(r'[:.]'), '-');
    final file = File(p.join(backupsDir.path, 'mobile_shop_backup_$stamp.json'));
    await file.writeAsString(const JsonEncoder.withIndent('  ').convert(payload.toJson()));
    return file;
  }

  /// Parses [file] as a backup and restores it, wiping current local
  /// records first so the device ends up matching the file exactly (no
  /// mixing old and restored rows). Throws [FormatException] if the file
  /// isn't a recognizable backup.
  Future<BackupImportResult> importFromFile(File file) async {
    final content = await file.readAsString();
    late final Map<String, dynamic> decoded;
    try {
      decoded = jsonDecode(content) as Map<String, dynamic>;
    } on FormatException {
      throw const FormatException('الملف المختار ليس ملف نسخة احتياطية صالح (JSON غير سليم).');
    }
    final payload = BackupPayload.fromJson(decoded);
    if (payload.schemaVersion > _currentSchemaVersion) {
      throw const FormatException('هذه النسخة الاحتياطية تم إنشاؤها بإصدار أحدث من التطبيق غير مدعوم هنا.');
    }

    await _store.clearAllRecords();
    for (final r in payload.records) {
      final rawPayload = r['payload'];
      if (r['entity'] is! String || r['record_id'] is! String || rawPayload is! Map) {
        continue; // skip malformed rows rather than fail the whole restore
      }
      await _store.restoreRecord(
        entity: r['entity'] as String,
        recordId: r['record_id'] as String,
        tenantId: r['tenant_id'] as String? ?? LocalStore.defaultTenantId,
        branchId: r['branch_id'] as String? ?? LocalStore.defaultBranchId,
        payload: rawPayload.cast<String, dynamic>(),
        version: r['version'] as int? ?? 1,
      );
    }
    return BackupImportResult(recordCount: payload.records.length, exportedAt: payload.exportedAt);
  }
}

Future<BackupService> getBackupService() async {
  final store = await LocalStore.open();
  return BackupService(store);
}
