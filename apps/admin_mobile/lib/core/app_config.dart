import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

/// Persists Online mode config in a tiny SQLite settings table.
/// Avoids adding shared_preferences to pubspec just for 3 keys.
class AppConfig {
  AppConfig._({
    required this.onlineMode,
    required this.apiUrl,
    required this.apiToken,
  });

  bool onlineMode;
  String apiUrl;
  String apiToken;

  static const _defaultUrl = 'http://localhost:8000';
  static const _defaultToken = 'dev-owner-token';

  static Database? _db;
  static AppConfig? _instance;

  static Future<AppConfig> load() async {
    if (_instance != null) return _instance!;
    _db ??= await _openDb();
    final rows = await _db!.query('settings');
    final map = {for (final r in rows) r['key'] as String: r['value'] as String};
    _instance = AppConfig._(
      onlineMode: map['online_mode'] == '1',
      apiUrl: map['api_url'] ?? _defaultUrl,
      apiToken: map['api_token'] ?? _defaultToken,
    );
    return _instance!;
  }

  Future<void> save() async {
    _db ??= await _openDb();
    final batch = _db!.batch();
    for (final entry in {
      'online_mode': onlineMode ? '1' : '0',
      'api_url': apiUrl,
      'api_token': apiToken,
    }.entries) {
      batch.insert(
        'settings',
        {'key': entry.key, 'value': entry.value},
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  static Future<Database> _openDb() async {
    final path = join(await getDatabasesPath(), 'app_config.db');
    return openDatabase(
      path,
      version: 1,
      onCreate: (db, _) => db.execute(
        'CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
      ),
    );
  }

  /// Call when toggling Online mode — clears cached repo instances so next
  /// call to getXRepository() picks up the new mode.
  static void invalidateRepositoryCache() {
    _instance = null;
  }
}
