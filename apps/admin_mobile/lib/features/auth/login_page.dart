import 'package:flutter/material.dart';
import 'auth_models.dart';
import 'auth_service.dart';

/// شاشة تسجيل الدخول — تظهر لما يكون مفيش جلسة محفوظة.
/// بعد نجاح الدخول بتنادي [onLoggedIn].
class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.onLoggedIn});
  final void Function(AccountSession session) onLoggedIn;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final _urlCtrl = TextEditingController(text: 'https://');
  final _emailCtrl = TextEditingController();
  final _passCtrl = TextEditingController();

  bool _loading = false;
  bool _obscurePass = true;
  String? _error;

  @override
  void dispose() {
    _urlCtrl.dispose();
    _emailCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final session = await AuthService.instance.login(
        apiUrl: _urlCtrl.text.trim(),
        email: _emailCtrl.text.trim(),
        password: _passCtrl.text,
        onSelectBranch: (branches) => _pickBranch(branches),
      );
      if (mounted) widget.onLoggedIn(session);
    } on AuthException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = 'خطأ غير متوقع: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<BranchInfo> _pickBranch(List<BranchInfo> branches) async {
    final picked = await showDialog<BranchInfo>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => Directionality(
        textDirection: TextDirection.rtl,
        child: AlertDialog(
          title: const Text('اختر الفرع'),
          content: SizedBox(
            width: double.maxFinite,
            child: ListView.separated(
              shrinkWrap: true,
              itemCount: branches.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) => ListTile(
                title: Text(branches[i].name),
                subtitle: Text(branches[i].id,
                    style: const TextStyle(fontSize: 11, color: Colors.black45)),
                onTap: () => Navigator.pop(ctx, branches[i]),
              ),
            ),
          ),
        ),
      ),
    );
    if (picked == null) throw AuthException('لم يتم اختيار فرع.');
    return picked;
  }

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF0B1220);
    const gold = Color(0xFFD6A84F);

    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: const Color(0xFFF7F8FA),
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // ── Logo ─────────────────────────────────────────────
                    Center(
                      child: Container(
                        width: 80,
                        height: 80,
                        decoration: BoxDecoration(
                          color: navy,
                          borderRadius: BorderRadius.circular(22),
                        ),
                        child: const Icon(Icons.phone_android_rounded,
                            color: gold, size: 40),
                      ),
                    ),
                    const SizedBox(height: 18),
                    const Center(
                      child: Text('Mobile Shop',
                          style: TextStyle(
                              fontSize: 26,
                              fontWeight: FontWeight.w900,
                              color: navy)),
                    ),
                    const Center(
                      child: Text('تسجيل الدخول للحساب السحابي',
                          style: TextStyle(color: Colors.black54)),
                    ),
                    const SizedBox(height: 32),

                    // ── Fields ───────────────────────────────────────────
                    _Field(
                      controller: _urlCtrl,
                      label: 'عنوان السيرفر (API URL)',
                      hint: 'https://your-api.com',
                      icon: Icons.link_rounded,
                      keyboardType: TextInputType.url,
                      validator: (v) {
                        if (v == null || v.trim().isEmpty) return 'مطلوب';
                        if (!v.startsWith('http')) return 'يجب أن يبدأ بـ https://';
                        return null;
                      },
                    ),
                    const SizedBox(height: 12),
                    _Field(
                      controller: _emailCtrl,
                      label: 'البريد الإلكتروني',
                      hint: 'example@shop.com',
                      icon: Icons.email_outlined,
                      keyboardType: TextInputType.emailAddress,
                      validator: (v) {
                        if (v == null || v.trim().isEmpty) return 'مطلوب';
                        if (!v.contains('@')) return 'بريد إلكتروني غير صالح';
                        return null;
                      },
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _passCtrl,
                      obscureText: _obscurePass,
                      textDirection: TextDirection.ltr,
                      decoration: InputDecoration(
                        labelText: 'كلمة المرور',
                        prefixIcon: const Icon(Icons.lock_outline_rounded),
                        suffixIcon: IconButton(
                          icon: Icon(_obscurePass
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined),
                          onPressed: () =>
                              setState(() => _obscurePass = !_obscurePass),
                        ),
                      ),
                      validator: (v) =>
                          (v == null || v.isEmpty) ? 'مطلوب' : null,
                    ),
                    const SizedBox(height: 8),

                    // ── Error ────────────────────────────────────────────
                    if (_error != null) ...[
                      const SizedBox(height: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFEBEB),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(children: [
                          const Icon(Icons.error_outline_rounded,
                              color: Colors.red, size: 18),
                          const SizedBox(width: 8),
                          Expanded(
                              child: Text(_error!,
                                  style: const TextStyle(
                                      color: Colors.red, fontSize: 13))),
                        ]),
                      ),
                    ],
                    const SizedBox(height: 20),

                    // ── Submit ───────────────────────────────────────────
                    SizedBox(
                      height: 52,
                      child: FilledButton(
                        onPressed: _loading ? null : _submit,
                        style: FilledButton.styleFrom(
                          backgroundColor: navy,
                          shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14)),
                        ),
                        child: _loading
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2, color: Colors.white),
                              )
                            : const Text('تسجيل الدخول',
                                style: TextStyle(
                                    fontSize: 16, fontWeight: FontWeight.bold)),
                      ),
                    ),
                    const SizedBox(height: 24),

                    // ── Offline note ─────────────────────────────────────
                    Center(
                      child: TextButton.icon(
                        onPressed: () => _showOfflineInfo(),
                        icon: const Icon(Icons.cloud_off_rounded,
                            size: 16, color: Colors.black45),
                        label: const Text('العمل بدون اتصال (Offline)',
                            style: TextStyle(color: Colors.black45)),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _showOfflineInfo() {
    showDialog<void>(
      context: context,
      builder: (ctx) => Directionality(
        textDirection: TextDirection.rtl,
        child: AlertDialog(
          title: const Text('العمل بدون اتصال'),
          content: const Text(
            'يمكنك استخدام التطبيق بالكامل بدون تسجيل دخول — '
            'كل البيانات تُحفظ محلياً على هذا الجهاز.\n\n'
            'تسجيل الدخول يُتيح مزامنة البيانات مع السيرفر المركزي '
            'والوصول من أجهزة متعددة.',
          ),
          actions: [
            FilledButton(
              onPressed: () {
                Navigator.pop(ctx);
                // العودة للتطبيق في Offline mode
                widget.onLoggedIn(_offlineSession());
              },
              child: const Text('متابعة بدون اتصال'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('إلغاء'),
            ),
          ],
        ),
      ),
    );
  }

  /// جلسة وهمية للـ Offline mode — نفس القيم الافتراضية اللي في LocalStore.
  static AccountSession _offlineSession() => AccountSession(
        tenantId: 'LOCAL_TENANT',
        accountId: 'LOCAL_ACCOUNT',
        email: '',
        displayName: 'وضع محلي',
        token: '',
        branchId: 'LOCAL_BRANCH',
        branchName: 'الفرع المحلي',
        apiUrl: '',
      );
}

class _Field extends StatelessWidget {
  const _Field({
    required this.controller,
    required this.label,
    required this.hint,
    required this.icon,
    this.keyboardType,
    this.validator,
  });

  final TextEditingController controller;
  final String label;
  final String hint;
  final IconData icon;
  final TextInputType? keyboardType;
  final String? Function(String?)? validator;

  @override
  Widget build(BuildContext context) => TextFormField(
        controller: controller,
        keyboardType: keyboardType,
        textDirection: TextDirection.ltr,
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          prefixIcon: Icon(icon),
        ),
        validator: validator,
      );
}
