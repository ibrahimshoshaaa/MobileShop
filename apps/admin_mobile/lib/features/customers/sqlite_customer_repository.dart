import 'dart:math';
import '../inventory/local_store.dart';
import 'customer_models.dart';
import 'customer_repository.dart';
import '../sync/online_push.dart';

class SqliteCustomerRepository implements CustomerRepository {
  SqliteCustomerRepository._(this._store);
  final LocalStore _store;
  static const _entity = 'customer';

  static Future<SqliteCustomerRepository> create() async {
    final store = await LocalStore.open();
    return SqliteCustomerRepository._(store);
  }

  Customer _toCustomer(Map<String, dynamic> payload) => Customer(
        id: payload['id'] as String,
        name: payload['name'] as String,
        phone: payload['phone'] as String?,
        active: (payload['active'] as bool?) ?? true,
      );

  Map<String, dynamic> _toPayload(Customer c) => {
        'id': c.id,
        'name': c.name,
        'phone': c.phone,
        'active': c.active,
      };

  @override
  Future<List<Customer>> listCustomers({String query = ''}) async {
    final rows = await _store.listRecords(entity: _entity);
    final q = query.trim().toLowerCase();
    return rows.map((r) => _toCustomer(r.payload)).where((c) {
      if (q.isEmpty) return true;
      return c.name.toLowerCase().contains(q) || (c.phone?.contains(q) ?? false);
    }).toList(growable: false);
  }

  @override
  Future<Customer?> getCustomer(String id) async {
    final row = await _store.getRecord(entity: _entity, recordId: id);
    if (row == null) return null;
    return _toCustomer(row.payload);
  }

  @override
  Future<Customer> addCustomer({required String name, String? phone}) async {
    if (name.trim().isEmpty) throw CustomerException('اسم العميل مطلوب.');
    final cleanPhone = (phone == null || phone.trim().isEmpty) ? null : phone.trim();
    if (cleanPhone != null) {
      final existing = await listCustomers();
      if (existing.any((c) => c.phone == cleanPhone)) {
        throw CustomerException('يوجد عميل آخر بنفس رقم الهاتف.');
      }
    }
    final customer = Customer(id: _newId(), name: name.trim(), phone: cleanPhone);
    await _store.upsertRecord(entity: _entity, recordId: customer.id, payload: _toPayload(customer), expectedVersion: 0);
    final createCmdId = _newId(prefix: 'cmd-create-customer');
    await _store.queueCommand(commandId: createCmdId, command: 'createCustomer', payload: _toPayload(customer));
    await pushCommandOnline(_store, createCmdId, 'createCustomer', _toPayload(customer));
    return customer;
  }

  @override
  Future<Customer> updateCustomer(Customer customer) async {
    final current = await _store.getRecord(entity: _entity, recordId: customer.id);
    if (current == null) throw CustomerException('العميل غير موجود.');
    if (customer.name.trim().isEmpty) throw CustomerException('اسم العميل مطلوب.');
    if (customer.phone != null) {
      final others = await listCustomers();
      final clash = others.any((c) => c.id != customer.id && c.phone == customer.phone);
      if (clash) throw CustomerException('يوجد عميل آخر بنفس رقم الهاتف.');
    }
    try {
      await _store.upsertRecord(
        entity: _entity,
        recordId: customer.id,
        payload: _toPayload(customer),
        expectedVersion: current.version,
      );
    } on StaleVersionException catch (e) {
      throw CustomerException(e.toString());
    }
    final updateCmdId = _newId(prefix: 'cmd-update-customer');
    await _store.queueCommand(commandId: updateCmdId, command: 'updateCustomer', payload: _toPayload(customer));
    await pushCommandOnline(_store, updateCmdId, 'updateCustomer', _toPayload(customer));
    return customer;
  }

  String _newId({String prefix = 'cust'}) => '$prefix-${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(999999)}';
}
