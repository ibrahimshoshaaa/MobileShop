import 'dart:math';
import '../inventory/local_store.dart';
import 'supplier_models.dart';
import 'supplier_repository.dart';

class SqliteSupplierRepository implements SupplierRepository {
  SqliteSupplierRepository._(this._store);
  final LocalStore _store;
  static const _entity = 'supplier';

  static Future<SqliteSupplierRepository> create() async {
    final store = await LocalStore.open();
    return SqliteSupplierRepository._(store);
  }

  Supplier _toSupplier(Map<String, dynamic> payload) => Supplier(
        id: payload['id'] as String,
        name: payload['name'] as String,
        phone: payload['phone'] as String?,
        active: (payload['active'] as bool?) ?? true,
      );

  Map<String, dynamic> _toPayload(Supplier s) => {
        'id': s.id,
        'name': s.name,
        'phone': s.phone,
        'active': s.active,
      };

  @override
  Future<List<Supplier>> listSuppliers({String query = ''}) async {
    final rows = await _store.listRecords(entity: _entity);
    final q = query.trim().toLowerCase();
    final suppliers = rows.map((r) => _toSupplier(r.payload)).where((s) {
      if (q.isEmpty) return true;
      return s.name.toLowerCase().contains(q) || (s.phone?.contains(q) ?? false);
    }).toList();
    suppliers.sort((a, b) => a.name.compareTo(b.name));
    return suppliers;
  }

  @override
  Future<Supplier> addSupplier({required String name, String? phone}) async {
    if (name.trim().isEmpty) throw SupplierException('اسم المورد مطلوب.');
    final cleanPhone = (phone == null || phone.trim().isEmpty) ? null : phone.trim();
    if (cleanPhone != null) {
      final existing = await listSuppliers();
      if (existing.any((s) => s.phone == cleanPhone)) {
        throw SupplierException('يوجد مورد آخر بنفس رقم الهاتف.');
      }
    }
    final supplier = Supplier(id: _newId(), name: name.trim(), phone: cleanPhone);
    await _store.upsertRecord(entity: _entity, recordId: supplier.id, payload: _toPayload(supplier), expectedVersion: 0);
    await _store.queueCommand(
      commandId: _newId(prefix: 'cmd-create-supplier'),
      command: 'createSupplier',
      payload: _toPayload(supplier),
    );
    return supplier;
  }

  @override
  Future<Supplier> updateSupplier(Supplier supplier) async {
    // Note: no 'updateSupplier' command exists in the backend's dispatch
    // table yet (only 'createSupplier' does — same gap as wallets before
    // createWallet was added), so this only updates local state and isn't
    // queued for sync yet.
    final current = await _store.getRecord(entity: _entity, recordId: supplier.id);
    if (current == null) throw SupplierException('المورد غير موجود.');
    if (supplier.name.trim().isEmpty) throw SupplierException('اسم المورد مطلوب.');
    if (supplier.phone != null) {
      final others = await listSuppliers();
      final clash = others.any((s) => s.id != supplier.id && s.phone == supplier.phone);
      if (clash) throw SupplierException('يوجد مورد آخر بنفس رقم الهاتف.');
    }
    try {
      await _store.upsertRecord(
        entity: _entity,
        recordId: supplier.id,
        payload: _toPayload(supplier),
        expectedVersion: current.version,
      );
    } on StaleVersionException catch (e) {
      throw SupplierException(e.toString());
    }
    return supplier;
  }

  String _newId({String prefix = 'sup'}) => '$prefix-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(999999)}';
}
