import '../sync/api_client.dart';
import 'supplier_models.dart';
import 'supplier_repository.dart';

/// Server-backed [SupplierRepository] — 4.2 ("قراءة البيانات ... من
/// السيرفر"). [listSuppliers] calls `GET /query/suppliers` via [ApiClient]
/// instead of the local SQLite table.
///
/// The server's `Supplier` also carries `branch_ids` (see
/// `shared/models/erp.py`), but the mobile [Supplier] model deliberately
/// omits that field — same reasoning as the offline model already
/// documents (no branch-selection UI exists yet) — so it's read and
/// discarded here, not because it's unavailable.
///
/// Writing a supplier isn't part of 4.2 or 4.3, so [addSupplier]/
/// [updateSupplier] delegate to [_local] (the existing offline SQLite
/// repository) unchanged — only the supplier *list* comes from the server
/// when there's an active session.
class ApiSupplierRepository implements SupplierRepository {
  ApiSupplierRepository(this._client, this._local);

  final ApiClient _client;
  final SupplierRepository _local;

  Supplier _fromJson(Map<String, dynamic> j) => Supplier(
        id: j['id'] as String,
        name: j['name'] as String,
        phone: j['phone'] as String?,
        active: j['active'] as bool? ?? true,
      );

  @override
  Future<List<Supplier>> listSuppliers({String query = ''}) async {
    final List<Map<String, dynamic>> raw;
    try {
      raw = await _client.getSuppliers(limit: 500);
    } on ApiException catch (e) {
      throw SupplierException(e.message);
    }
    final q = query.trim().toLowerCase();
    final suppliers = raw.map(_fromJson).where((s) {
      if (q.isEmpty) return true;
      return s.name.toLowerCase().contains(q) || (s.phone?.contains(q) ?? false);
    }).toList()
      ..sort((a, b) => a.name.compareTo(b.name));
    return suppliers;
  }

  @override
  Future<Supplier> addSupplier({required String name, String? phone}) =>
      _local.addSupplier(name: name, phone: phone);

  @override
  Future<Supplier> updateSupplier(Supplier supplier) => _local.updateSupplier(supplier);
}
