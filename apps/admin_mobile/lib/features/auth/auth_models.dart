import 'dart:convert';

/// بيانات الحساب المحفوظة بعد تسجيل الدخول.
/// بتتحفظ في SQLite settings وبتتقرأ عند بدء التطبيق.
class AccountSession {
  AccountSession({
    required this.tenantId,
    required this.accountId,
    required this.email,
    required this.displayName,
    required this.token,
    required this.branchId,
    required this.branchName,
    required this.apiUrl,
  });

  final String tenantId;
  final String accountId;
  final String email;
  final String displayName;
  final String token;
  final String branchId;
  final String branchName;
  final String apiUrl;

  Map<String, dynamic> toJson() => {
        'tenant_id': tenantId,
        'account_id': accountId,
        'email': email,
        'display_name': displayName,
        'token': token,
        'branch_id': branchId,
        'branch_name': branchName,
        'api_url': apiUrl,
      };

  factory AccountSession.fromJson(Map<String, dynamic> j) => AccountSession(
        tenantId: j['tenant_id'] as String,
        accountId: j['account_id'] as String,
        email: j['email'] as String,
        displayName: j['display_name'] as String,
        token: j['token'] as String,
        branchId: j['branch_id'] as String,
        branchName: j['branch_name'] as String,
        apiUrl: j['api_url'] as String,
      );

  String toJsonString() => jsonEncode(toJson());
  static AccountSession fromJsonString(String s) =>
      AccountSession.fromJson(jsonDecode(s) as Map<String, dynamic>);
}

/// فرع يرجع من السيرفر عند تسجيل الدخول.
class BranchInfo {
  BranchInfo({required this.id, required this.name});
  final String id;
  final String name;

  factory BranchInfo.fromJson(Map<String, dynamic> j) => BranchInfo(
        id: j['id'] as String,
        name: j['name'] as String? ?? j['id'] as String,
      );
}
