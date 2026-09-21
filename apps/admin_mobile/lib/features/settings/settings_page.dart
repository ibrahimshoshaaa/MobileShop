import 'package:flutter/material.dart';
import '../../core/app_config.dart';
import '../../core/repository_factory.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  bool _loading = true;
  late bool _onlineMode;
  final _urlController = TextEditingController();
  final _tokenController = TextEditingController();
  bool _saving = false;
  String? _saveError;
  String? _saveSuccess;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final cfg = await AppConfig.load();
    if (!mounted) return;
    setState(() {
      _onlineMode = cfg.onlineMode;
      _urlController.text = cfg.apiUrl;
      _tokenController.text = cfg.apiToken;
      _loading = false;
    });
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _saveError = null;
      _saveSuccess = null;
    });
    try {
      final cfg = await AppConfig.load();
      cfg.onlineMode = _onlineMode;
      cfg.apiUrl = _urlController.text.trim().isEmpty
          ? 'http://localhost:8000'
          : _urlController.text.trim();
      cfg.apiToken = _tokenController.text.trim().isEmpty
          ? 'dev-owner-token'
          : _tokenController.text.trim();
      await cfg.save();
      resetAllRepositories();
      if (mounted) {
        setState(() => _saveSuccess = 'تم الحفظ — أعد تشغيل الصفحة لتفعيل الوضع الجديد.');
      }
    } catch (e) {
      if (mounted) setState(() => _saveError = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  void dispose() {
    _urlController.dispose();
    _tokenController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
      children: [
        // ── وضع التشغيل ─────────────────────────────────────
        const Text('وضع التشغيل',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
        const SizedBox(height: 10),
        Card(
          child: Column(
            children: [
              SwitchListTile(
                value: _onlineMode,
                onChanged: (v) => setState(() {
                  _onlineMode = v;
                  _saveSuccess = null;
                  _saveError = null;
                }),
                title: Text(
                  _onlineMode ? 'Online' : 'Offline',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                subtitle: Text(
                  _onlineMode
                      ? 'البيانات تُرسل مباشرة للسيرفر المركزي'
                      : 'البيانات تُحفظ محلياً على الجهاز',
                ),
                secondary: Icon(
                  _onlineMode ? Icons.cloud_done_rounded : Icons.cloud_off_rounded,
                  color: _onlineMode
                      ? const Color(0xFF0B1220)
                      : Colors.black45,
                ),
              ),
              if (_onlineMode) ...[
                const Divider(height: 1),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
                  child: TextField(
                    controller: _urlController,
                    decoration: const InputDecoration(
                      labelText: 'عنوان API',
                      hintText: 'http://localhost:8000',
                      prefixIcon: Icon(Icons.link_rounded),
                    ),
                    keyboardType: TextInputType.url,
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
                  child: TextField(
                    controller: _tokenController,
                    decoration: const InputDecoration(
                      labelText: 'Token',
                      hintText: 'dev-owner-token',
                      prefixIcon: Icon(Icons.vpn_key_rounded),
                    ),
                    obscureText: true,
                  ),
                ),
              ],
            ],
          ),
        ),

        // ── رسائل ─────────────────────────────────────────
        if (_saveError != null) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFFFFEBEB),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(children: [
              const Icon(Icons.error_outline_rounded, color: Colors.red, size: 18),
              const SizedBox(width: 8),
              Expanded(
                  child: Text(_saveError!,
                      style: const TextStyle(color: Colors.red, fontSize: 13))),
            ]),
          ),
        ],
        if (_saveSuccess != null) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFFE8F5E9),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(children: [
              const Icon(Icons.check_circle_outline_rounded,
                  color: Colors.green, size: 18),
              const SizedBox(width: 8),
              Expanded(
                  child: Text(_saveSuccess!,
                      style: const TextStyle(color: Colors.green, fontSize: 13))),
            ]),
          ),
        ],

        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _saving ? null : _save,
          icon: _saving
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: Colors.white),
                )
              : const Icon(Icons.save_rounded),
          label: Text(_saving ? 'جارٍ الحفظ...' : 'حفظ الإعدادات'),
        ),

        // ── روابط سريعة أخرى ─────────────────────────────
        const SizedBox(height: 24),
        const Text('الحساب والأمان',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
        const SizedBox(height: 10),
        const Card(
          child: Column(children: [
            ListTile(
              leading: Icon(Icons.account_circle_outlined),
              title: Text('حساب الشركة'),
              subtitle: Text('تسجيل الدخول وربط الفروع'),
              trailing: Icon(Icons.chevron_left_rounded),
            ),
            Divider(height: 1),
            ListTile(
              leading: Icon(Icons.backup_outlined),
              title: Text('النسخ الاحتياطي'),
              subtitle: Text('إعدادات النسخ والاسترجاع'),
              trailing: Icon(Icons.chevron_left_rounded),
            ),
            Divider(height: 1),
            ListTile(
              leading: Icon(Icons.security_outlined),
              title: Text('الأمان والصلاحيات'),
              subtitle: Text('المستخدمون والأدوار وسجل التدقيق'),
              trailing: Icon(Icons.chevron_left_rounded),
            ),
          ]),
        ),
      ],
    );
  }
}
