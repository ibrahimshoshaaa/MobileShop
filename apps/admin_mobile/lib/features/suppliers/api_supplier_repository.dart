import '../suppliers/supplier_models.dart';
import '../suppliers/supplier_repository.dart';
import '../../core/api_client.dart';

class ApiSupplierRepository implements SupplierRepository {
  ApiSupplierRepository({required this.client});
  final ApiClient client;

  Supplier _toSupplier(Map<String, dynamic> d) => Supplier(
        id: d['id'] as String,
        name: d['name'] as String,
        phone: d['phone'] as String?,
        active: d['active'] as bool? ?? true,
      );

  @override
  Future<List<Supplier>> listSuppliers({String query = ''}) async {
    final raw = await client.query('suppliers');
    final all = raw.map(_toSupplier).toList();
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return all..sort((a, b) => a.name.compareTo(b.name));
    return all
        .where((s) =>
            s.name.toLowerCase().contains(q) ||
            (s.phone?.contains(q) ?? false))
        .toList()
      ..sort((a, b) => a.name.compareTo(b.name));
  }

  @override
  Future<Supplier> addSupplier({required String name, String? phone}) async {
    if (name.trim().isEmpty) throw SupplierException('اسم المورد مطلوب.');
    final data = await client.command(
      ApiClient.newCommandId('cmd-create-supplier'),
      'createSupplier',
      {
        'name': name.trim(),
        'phone': (phone?.trim().isEmpty ?? true) ? null : phone!.trim(),
        'branch_ids': [client.branchId],
      },
    );
    return _toSupplier(data);
  }

  @override
  Future<Supplier> updateSupplier(Supplier supplier) async {
    if (supplier.name.trim().isEmpty) throw SupplierException('اسم المورد مطلوب.');
    final data = await client.command(
      ApiClient.newCommandId('cmd-update-supplier'),
      'updateSupplier',
      {
        'supplier_id': supplier.id,
        'changes': {
          'name': supplier.name.trim(),
          'phone': (supplier.phone?.trim().isEmpty ?? true)
              ? null
              : supplier.phone!.trim(),
          'active': supplier.active,
        },
      },
    );
    return _toSupplier(data);
  }
}
